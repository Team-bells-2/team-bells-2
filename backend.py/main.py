from __future__ import annotations

import os
import json
import sqlite3
import asyncio
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from ai_extractor import extract_message
from local_whisper import transcribe_audio
from market_data import DATA_NOTICE, MARKETS, available_products, recommend_market
from schemas import (
	AskRequest,
	CustomerBalance,
	Entry,
	EntryCreate,
	EntryType,
	InventoryItem,
	MarketListResponse,
	MarketRecommendationRequest,
	MarketRecommendationResponse,
	MarketReviewCreate,
	MarketReviewResponse,
	MarketReviewsResponse,
	MessageRequest,
	ProfitReport,
	StockInRequest,
)
from weather_forecast import OPEN_METEO_ATTRIBUTION, fetch_lagos_market_forecasts


DEFAULT_DB_PATH = Path(__file__).with_name("sabimarket.sqlite3")


def create_app(
	database_path: str | Path | None = None,
	message_extractor: Callable[..., dict[str, Any]] | None = None,
	audio_transcriber: Callable[..., dict[str, str | None]] | None = None,
	weather_fetcher: Callable[..., Any] | None = None,
) -> FastAPI:
	db_path = Path(database_path or os.getenv("SABIMARKET_DB_PATH", DEFAULT_DB_PATH))

	def connect() -> sqlite3.Connection:
		connection = sqlite3.connect(db_path)
		connection.row_factory = sqlite3.Row
		connection.execute("PRAGMA foreign_keys = ON")
		return connection

	def get_connection():
		with closing(connect()) as connection:
			yield connection

	db_path.parent.mkdir(parents=True, exist_ok=True)
	with closing(connect()) as connection:
		connection.executescript(
			"""
			CREATE TABLE IF NOT EXISTS entries (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				type TEXT NOT NULL CHECK (type IN ('sale', 'credit_sale', 'payment_received', 'expense')),
				item TEXT,
				quantity REAL,
				unit TEXT,
				amount_ngn INTEGER NOT NULL CHECK (amount_ngn >= 0),
				customer TEXT,
				due_date TEXT,
				confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
				raw_text TEXT,
				cost_of_goods_ngn INTEGER,
				created_at TEXT NOT NULL
			);
			CREATE INDEX IF NOT EXISTS entries_created_at_idx ON entries(created_at DESC);
			CREATE INDEX IF NOT EXISTS entries_customer_idx ON entries(customer);
			CREATE TABLE IF NOT EXISTS inventory_items (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				item TEXT NOT NULL COLLATE NOCASE UNIQUE,
				unit TEXT NOT NULL,
				quantity_on_hand REAL NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
				unit_cost_ngn REAL NOT NULL DEFAULT 0 CHECK (unit_cost_ngn >= 0),
				reorder_level REAL NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
				updated_at TEXT NOT NULL
			);
			CREATE TABLE IF NOT EXISTS inventory_movements (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				inventory_item_id INTEGER NOT NULL REFERENCES inventory_items(id),
				entry_id INTEGER REFERENCES entries(id),
				movement_type TEXT NOT NULL CHECK (movement_type IN ('stock_in', 'sale')),
				quantity REAL NOT NULL CHECK (quantity > 0),
				unit_cost_ngn REAL NOT NULL CHECK (unit_cost_ngn >= 0),
				created_at TEXT NOT NULL
			);
			CREATE TABLE IF NOT EXISTS conversation_state (
				conversation_id TEXT PRIMARY KEY,
				last_entry_id INTEGER REFERENCES entries(id),
				pending_message TEXT,
				updated_at TEXT NOT NULL
			);
			CREATE TABLE IF NOT EXISTS entry_revisions (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				entry_id INTEGER NOT NULL REFERENCES entries(id),
				previous_entry_json TEXT NOT NULL,
				correction_text TEXT NOT NULL,
				corrected_at TEXT NOT NULL
			);
			CREATE TABLE IF NOT EXISTS market_reviews (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				market_id TEXT NOT NULL,
				product TEXT NOT NULL COLLATE NOCASE,
				reviewer_id TEXT NOT NULL,
				rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
				review_text TEXT NOT NULL,
				created_at TEXT NOT NULL,
				UNIQUE (market_id, product, reviewer_id)
			);
			CREATE INDEX IF NOT EXISTS market_reviews_product_idx ON market_reviews(product, market_id);
			"""
		)
		entry_columns = {
			row["name"] for row in connection.execute("PRAGMA table_info(entries)")
		}
		if "cost_of_goods_ngn" not in entry_columns:
			connection.execute("ALTER TABLE entries ADD COLUMN cost_of_goods_ngn INTEGER")

	app = FastAPI(title="OJA Prototype API", version="0.2.0")
	extractor = message_extractor or extract_message
	transcriber = audio_transcriber or transcribe_audio
	get_forecasts = weather_fetcher or fetch_lagos_market_forecasts

	def correct_entry(
		entry_id: int,
		correction: dict[str, Any],
		correction_text: str,
		connection: sqlite3.Connection,
	) -> Entry:
		connection.execute("BEGIN IMMEDIATE")
		try:
			previous_row = connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
			if previous_row is None:
				raise HTTPException(status_code=409, detail="The entry to correct no longer exists.")
			previous = dict(previous_row)
			updated_data = {
				key: previous[key]
				for key in (
					"type", "item", "quantity", "unit", "amount_ngn", "customer",
					"due_date", "confidence", "raw_text",
				)
			}
			updated_data.update(correction)
			updated_data["raw_text"] = correction_text
			updated_entry = EntryCreate(**updated_data)
			connection.execute(
				"INSERT INTO entry_revisions (entry_id, previous_entry_json, correction_text, corrected_at) VALUES (?, ?, ?, ?)",
				(entry_id, json.dumps(previous), correction_text, datetime.now(UTC).isoformat()),
			)

			old_inventory_item = None
			if previous["type"] in {"sale", "credit_sale"} and previous["item"]:
				old_inventory_item = connection.execute(
					"SELECT * FROM inventory_items WHERE item = ? COLLATE NOCASE", (previous["item"],)
				).fetchone()
			if old_inventory_item:
				connection.execute(
					"UPDATE inventory_items SET quantity_on_hand = quantity_on_hand + ? WHERE id = ?",
					(previous["quantity"] or 0, old_inventory_item["id"]),
				)
				connection.execute("DELETE FROM inventory_movements WHERE entry_id = ?", (entry_id,))

			new_inventory_item = None
			if updated_entry.type in {"sale", "credit_sale"} and updated_entry.item:
				new_inventory_item = connection.execute(
					"SELECT * FROM inventory_items WHERE item = ? COLLATE NOCASE", (updated_entry.item,)
				).fetchone()
			cost_of_goods_ngn = None
			if new_inventory_item:
				if updated_entry.quantity is None or updated_entry.unit is None:
					raise HTTPException(status_code=422, detail="Quantity and unit are required for tracked stock corrections.")
				if updated_entry.unit.casefold() != new_inventory_item["unit"].casefold():
					raise HTTPException(status_code=409, detail=f"Tracked item uses unit '{new_inventory_item['unit']}'.")
				if updated_entry.quantity > new_inventory_item["quantity_on_hand"]:
					raise HTTPException(status_code=409, detail="Correction would make tracked inventory negative.")
				cost_of_goods_ngn = round(updated_entry.quantity * new_inventory_item["unit_cost_ngn"])
				connection.execute(
					"UPDATE inventory_items SET quantity_on_hand = quantity_on_hand - ?, updated_at = ? WHERE id = ?",
					(updated_entry.quantity, datetime.now(UTC).isoformat(), new_inventory_item["id"]),
				)
				connection.execute(
					"INSERT INTO inventory_movements (inventory_item_id, entry_id, movement_type, quantity, unit_cost_ngn, created_at) VALUES (?, ?, 'sale', ?, ?, ?)",
					(new_inventory_item["id"], entry_id, updated_entry.quantity, new_inventory_item["unit_cost_ngn"], datetime.now(UTC).isoformat()),
				)
			connection.execute(
				"""
				UPDATE entries SET type = ?, item = ?, quantity = ?, unit = ?, amount_ngn = ?,
				customer = ?, due_date = ?, confidence = ?, raw_text = ?, cost_of_goods_ngn = ?
				WHERE id = ?
				""",
				(
					updated_entry.type, updated_entry.item, updated_entry.quantity, updated_entry.unit,
					updated_entry.amount_ngn, updated_entry.customer, updated_entry.due_date,
					updated_entry.confidence, updated_entry.raw_text, cost_of_goods_ngn, entry_id,
				),
			)
			connection.commit()
		except Exception:
			connection.rollback()
			raise
		row = connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
		return Entry(**dict(row))

	@app.get("/health")
	def health() -> dict[str, str]:
		return {"status": "ok"}

	def get_review_summaries(connection: sqlite3.Connection, product: str) -> dict[str, dict[str, float | int]]:
		rows = connection.execute(
			"""
			SELECT market_id, product, AVG(rating) AS average_rating, COUNT(*) AS review_count
			FROM market_reviews WHERE product = ? COLLATE NOCASE
			GROUP BY market_id, product
			""",
			(product,),
		).fetchall()
		return {
			f"{row['market_id']}:{row['product']}": {
				"average_rating": row["average_rating"],
				"review_count": row["review_count"],
			}
			for row in rows
		}

	@app.get("/markets", response_model=MarketListResponse)
	async def list_markets() -> dict[str, Any]:
		try:
			forecasts = await get_forecasts()
			health = "available"
		except Exception:
			forecasts = {}
			health = "unavailable"
		return {
			"data_notice": DATA_NOTICE,
			"products": available_products(),
			"weather_source": OPEN_METEO_ATTRIBUTION,
			"weather_status": health,
			"markets": [
				{
					"id": market_id,
					**market,
					"forecast": forecasts.get(market_id),
				}
				for market_id, market in MARKETS.items()
			],
		}

	@app.post("/markets/recommend", response_model=MarketRecommendationResponse)
	async def market_recommendation(request: MarketRecommendationRequest) -> dict[str, Any]:
		travel_date = request.travel_date or datetime.now(UTC).date()
		try:
			forecasts = await get_forecasts()
			weather_status = "available"
		except Exception:
			forecasts = {}
			weather_status = "unavailable"
		with closing(connect()) as connection:
			result = recommend_market(
				request.product,
				request.quantity,
				request.priority,
				get_review_summaries(connection, request.product),
				forecasts,
				travel_date.isoformat(),
			)
		if not result["ranked_offers"]:
			raise HTTPException(
				status_code=404,
				detail={"message": "No price offers found for this product.", "available_products": available_products()},
			)
		result["weather_status"] = weather_status
		return result

	@app.post("/markets/reviews", response_model=MarketReviewResponse, status_code=201)
	def submit_market_review(
		review: MarketReviewCreate,
		connection: sqlite3.Connection = Depends(get_connection),
	) -> dict[str, Any]:
		if review.market_id not in MARKETS:
			raise HTTPException(status_code=404, detail="Unknown market.")
		canonical_product = next(
			(product for product in available_products() if product.casefold() == review.product.casefold()),
			None,
		)
		if canonical_product is None:
			raise HTTPException(status_code=404, detail="Unknown product.")
		created_at = datetime.now(UTC).isoformat()
		connection.execute(
			"""
			INSERT INTO market_reviews (market_id, product, reviewer_id, rating, review_text, created_at)
			VALUES (?, ?, ?, ?, ?, ?)
			ON CONFLICT(market_id, product, reviewer_id) DO UPDATE SET
				rating = excluded.rating, review_text = excluded.review_text, created_at = excluded.created_at
			""",
			(review.market_id, canonical_product, review.reviewer_id.strip(), review.rating, review.review_text.strip(), created_at),
		)
		connection.commit()
		return {
			"status": "saved",
			"market_id": review.market_id,
			"product": canonical_product,
			"rating": review.rating,
			"review_text": review.review_text.strip(),
			"verified_purchase": False,
			"note": "Community-submitted and not purchase-verified.",
		}

	@app.get("/markets/reviews", response_model=MarketReviewsResponse)
	def list_market_reviews(
		product: str = Query(min_length=1, max_length=80),
		market_id: str | None = Query(default=None, max_length=50),
		connection: sqlite3.Connection = Depends(get_connection),
	) -> dict[str, Any]:
		if market_id:
			rows = connection.execute(
				"SELECT market_id, product, rating, review_text, created_at FROM market_reviews WHERE product = ? COLLATE NOCASE AND market_id = ? ORDER BY created_at DESC LIMIT 100",
				(product, market_id),
			).fetchall()
		else:
			rows = connection.execute(
				"SELECT market_id, product, rating, review_text, created_at FROM market_reviews WHERE product = ? COLLATE NOCASE ORDER BY created_at DESC LIMIT 100",
				(product,),
			).fetchall()
		return {
			"product": product,
			"verified_purchase": False,
			"reviews": [dict(row) for row in rows],
			"summary": get_review_summaries(connection, product),
		}

	@app.post("/transcribe")
	async def transcribe(request: Request, language: str | None = Query(default=None, max_length=12)) -> dict[str, str | None]:
		content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0].strip().casefold()
		audio = bytearray()
		async for chunk in request.stream():
			audio.extend(chunk)
			if len(audio) > 15 * 1024 * 1024:
				raise HTTPException(status_code=413, detail="Audio upload must be 15 MB or smaller.")
		try:
			result = await asyncio.to_thread(transcriber, bytes(audio), content_type, language)
		except ValueError as error:
			raise HTTPException(status_code=415, detail=str(error)) from error
		except RuntimeError as error:
			raise HTTPException(status_code=503, detail=str(error)) from error
		except Exception as error:
			raise HTTPException(status_code=502, detail="Local audio transcription failed.") from error
		return {"engine": "local-whisper", **result}

	@app.post("/entries", response_model=Entry, status_code=201)
	def create_entry(
		entry: EntryCreate, connection: sqlite3.Connection = Depends(get_connection)
	) -> Entry:
		created_at = datetime.now(UTC).isoformat()
		cost_of_goods_ngn = None
		connection.execute("BEGIN IMMEDIATE")
		try:
			inventory_item = None
			if entry.type in {"sale", "credit_sale"} and entry.item:
				inventory_item = connection.execute(
					"SELECT * FROM inventory_items WHERE item = ? COLLATE NOCASE",
					(entry.item,),
				).fetchone()
			if inventory_item:
				if entry.quantity is None or entry.unit is None:
					raise HTTPException(
						status_code=422,
						detail="Quantity and unit are required when selling a tracked inventory item.",
					)
				if entry.unit.casefold() != inventory_item["unit"].casefold():
					raise HTTPException(
						status_code=409,
						detail=f"Tracked item '{inventory_item['item']}' uses unit '{inventory_item['unit']}'.",
					)
				if entry.quantity > inventory_item["quantity_on_hand"]:
					raise HTTPException(
						status_code=409,
						detail=f"Not enough {inventory_item['item']} in stock to record this sale.",
					)
				cost_of_goods_ngn = round(entry.quantity * inventory_item["unit_cost_ngn"])

			cursor = connection.execute(
				"""
				INSERT INTO entries (
					type, item, quantity, unit, amount_ngn, customer,
					due_date, confidence, raw_text, cost_of_goods_ngn, created_at
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(
					entry.type,
					entry.item,
					entry.quantity,
					entry.unit,
					entry.amount_ngn,
					entry.customer,
					entry.due_date,
					entry.confidence,
					entry.raw_text,
					cost_of_goods_ngn,
					created_at,
				),
			)
			if inventory_item:
				connection.execute(
					"UPDATE inventory_items SET quantity_on_hand = quantity_on_hand - ?, updated_at = ? WHERE id = ?",
					(entry.quantity, created_at, inventory_item["id"]),
				)
				connection.execute(
					"""
					INSERT INTO inventory_movements (
						inventory_item_id, entry_id, movement_type, quantity, unit_cost_ngn, created_at
					) VALUES (?, ?, 'sale', ?, ?, ?)
					""",
					(inventory_item["id"], cursor.lastrowid, entry.quantity, inventory_item["unit_cost_ngn"], created_at),
				)
			connection.commit()
		except Exception:
			connection.rollback()
			raise
		row = connection.execute("SELECT * FROM entries WHERE id = ?", (cursor.lastrowid,)).fetchone()
		return Entry(**dict(row))

	@app.post("/messages")
	def process_message(
		request: MessageRequest,
		connection: sqlite3.Connection = Depends(get_connection),
	) -> dict[str, Any]:
		state = connection.execute(
			"SELECT * FROM conversation_state WHERE conversation_id = ?", (request.conversation_id,)
		).fetchone()
		context: dict[str, Any] = {}
		if state and state["pending_message"]:
			context["pending_message"] = state["pending_message"]
		if state and state["last_entry_id"]:
			last_entry = connection.execute("SELECT * FROM entries WHERE id = ?", (state["last_entry_id"],)).fetchone()
			if last_entry:
				context["last_entry"] = dict(last_entry)
		context["customers"] = [
			{"name": customer.name}
			for customer in list_customers(connection)
		]
		try:
			result = extractor(text=request.text, context=context)
		except RuntimeError as error:
			status_code = 503 if "not configured" in str(error).lower() else 502
			raise HTTPException(status_code=status_code, detail=str(error)) from error
		except Exception as error:
			raise HTTPException(status_code=502, detail="Message extraction failed.") from error

		status = result.get("status")
		if status == "needs_clarification":
			pending_message = context.get("pending_message", request.text)
			connection.execute(
				"""
				INSERT INTO conversation_state (conversation_id, last_entry_id, pending_message, updated_at)
				VALUES (?, ?, ?, ?)
				ON CONFLICT(conversation_id) DO UPDATE SET pending_message = excluded.pending_message, updated_at = excluded.updated_at
				""",
				(request.conversation_id, state["last_entry_id"] if state else None, pending_message, datetime.now(UTC).isoformat()),
			)
			connection.commit()
			return {
				"status": status,
				"conversation_id": request.conversation_id,
				"missing_fields": result.get("missing_fields", []),
				"question": result.get("question"),
			}

		if status == "corrected":
			if not state or not state["last_entry_id"]:
				raise HTTPException(status_code=409, detail="There is no recent entry in this conversation to correct.")
			entry_payload = result.get("entry")
			if not isinstance(entry_payload, dict):
				raise HTTPException(status_code=502, detail="Extractor returned an invalid correction.")
			updated_entry = correct_entry(state["last_entry_id"], entry_payload, request.text, connection)
			connection.execute(
				"UPDATE conversation_state SET pending_message = NULL, updated_at = ? WHERE conversation_id = ?",
				(datetime.now(UTC).isoformat(), request.conversation_id),
			)
			connection.commit()
			return {"status": "corrected", "entry": updated_entry.model_dump()}

		if status == "recorded" and isinstance(result.get("action"), dict):
			action = result["action"]
			if action.get("type") != "stock_in":
				raise HTTPException(status_code=502, detail="Extractor returned an unsupported business action.")
			try:
				inventory_item = stock_in(StockInRequest(**action), connection)
			except Exception as error:
				if isinstance(error, HTTPException):
					raise
				raise HTTPException(status_code=502, detail="Extractor returned an invalid stock-in action.") from error
			connection.execute(
				"""
				INSERT INTO conversation_state (conversation_id, last_entry_id, pending_message, updated_at)
				VALUES (?, NULL, NULL, ?)
				ON CONFLICT(conversation_id) DO UPDATE SET last_entry_id = NULL, pending_message = NULL, updated_at = excluded.updated_at
				""",
				(request.conversation_id, datetime.now(UTC).isoformat()),
			)
			connection.commit()
			return {"status": "recorded", "action": inventory_item.model_dump()}

		if status == "recorded" and isinstance(result.get("entry"), dict):
			entry_payload = dict(result["entry"])
			entry_payload["raw_text"] = context.get("pending_message", request.text)
			try:
				saved_entry = create_entry(EntryCreate(**entry_payload), connection)
			except Exception as error:
				if isinstance(error, HTTPException):
					raise
				raise HTTPException(status_code=502, detail="Extractor returned an incomplete or invalid entry.") from error
			connection.execute(
				"""
				INSERT INTO conversation_state (conversation_id, last_entry_id, pending_message, updated_at)
				VALUES (?, ?, NULL, ?)
				ON CONFLICT(conversation_id) DO UPDATE SET last_entry_id = excluded.last_entry_id, pending_message = NULL, updated_at = excluded.updated_at
				""",
				(request.conversation_id, saved_entry.id, datetime.now(UTC).isoformat()),
			)
			connection.commit()
			return {"status": "recorded", "entry": saved_entry.model_dump()}

		raise HTTPException(status_code=502, detail="Extractor returned an unsupported response.")

	@app.get("/entries", response_model=list[Entry])
	def list_entries(
		connection: sqlite3.Connection = Depends(get_connection),
		entry_type: EntryType | None = Query(default=None, alias="type"),
		limit: int = Query(default=50, ge=1, le=200),
		offset: int = Query(default=0, ge=0),
	) -> list[Entry]:
		if entry_type:
			rows = connection.execute(
				"SELECT * FROM entries WHERE type = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
				(entry_type, limit, offset),
			).fetchall()
		else:
			rows = connection.execute(
				"SELECT * FROM entries ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
				(limit, offset),
			).fetchall()
		return [Entry(**dict(row)) for row in rows]

	@app.post("/inventory/stock-in", response_model=InventoryItem, status_code=201)
	def stock_in(
		request: StockInRequest,
		connection: sqlite3.Connection = Depends(get_connection),
	) -> InventoryItem:
		created_at = datetime.now(UTC).isoformat()
		connection.execute("BEGIN IMMEDIATE")
		try:
			item = connection.execute(
				"SELECT * FROM inventory_items WHERE item = ? COLLATE NOCASE", (request.item.strip(),)
			).fetchone()
			if item and item["unit"].casefold() != request.unit.casefold():
				raise HTTPException(
					status_code=409,
					detail=f"Tracked item '{item['item']}' uses unit '{item['unit']}'.",
				)
			if item:
				new_quantity = item["quantity_on_hand"] + request.quantity
				weighted_cost = (
					item["quantity_on_hand"] * item["unit_cost_ngn"]
					+ request.quantity * request.unit_cost_ngn
				) / new_quantity
				connection.execute(
					"""
					UPDATE inventory_items
					SET quantity_on_hand = ?, unit_cost_ngn = ?, reorder_level = ?, updated_at = ?
					WHERE id = ?
					""",
					(new_quantity, weighted_cost, request.reorder_level, created_at, item["id"]),
				)
				item_id = item["id"]
			else:
				cursor = connection.execute(
					"""
					INSERT INTO inventory_items (item, unit, quantity_on_hand, unit_cost_ngn, reorder_level, updated_at)
					VALUES (?, ?, ?, ?, ?, ?)
					""",
					(request.item.strip(), request.unit.strip(), request.quantity, request.unit_cost_ngn, request.reorder_level, created_at),
				)
				item_id = cursor.lastrowid
			connection.execute(
				"""
				INSERT INTO inventory_movements (inventory_item_id, movement_type, quantity, unit_cost_ngn, created_at)
				VALUES (?, 'stock_in', ?, ?, ?)
				""",
				(item_id, request.quantity, request.unit_cost_ngn, created_at),
			)
			connection.commit()
		except Exception:
			connection.rollback()
			raise
		row = connection.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
		return InventoryItem(**dict(row))

	@app.get("/inventory", response_model=list[InventoryItem])
	def list_inventory(
		connection: sqlite3.Connection = Depends(get_connection),
	) -> list[InventoryItem]:
		rows = connection.execute(
			"SELECT * FROM inventory_items ORDER BY item COLLATE NOCASE"
		).fetchall()
		return [InventoryItem(**dict(row)) for row in rows]

	@app.get("/reports/profit", response_model=ProfitReport)
	def profit_report(
		start_date: date | None = None,
		end_date: date | None = None,
		connection: sqlite3.Connection = Depends(get_connection),
	) -> ProfitReport:
		end = end_date or datetime.now(UTC).date()
		start = start_date or end - timedelta(days=6)
		if start > end:
			raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
		start_at = datetime.combine(start, datetime.min.time(), UTC).isoformat()
		end_at = datetime.combine(end + timedelta(days=1), datetime.min.time(), UTC).isoformat()
		row = connection.execute(
			"""
			SELECT
				COALESCE(SUM(CASE WHEN type IN ('sale', 'credit_sale') THEN amount_ngn ELSE 0 END), 0) AS sales,
				COALESCE(SUM(CASE WHEN type = 'expense' THEN amount_ngn ELSE 0 END), 0) AS expenses,
				COALESCE(SUM(CASE WHEN type IN ('sale', 'credit_sale') THEN cost_of_goods_ngn ELSE 0 END), 0) AS cost_of_goods,
				SUM(CASE WHEN type IN ('sale', 'credit_sale') AND cost_of_goods_ngn IS NULL THEN 1 ELSE 0 END) AS uncosted_sales
			FROM entries WHERE created_at >= ? AND created_at < ?
			""",
			(start_at, end_at),
		).fetchone()
		sales = row["sales"]
		expenses = row["expenses"]
		cost_of_goods = row["cost_of_goods"]
		return ProfitReport(
			start_date=start.isoformat(),
			end_date=end.isoformat(),
			sales_ngn=sales,
			expenses_ngn=expenses,
			cost_of_goods_ngn=cost_of_goods,
			estimated_profit_ngn=sales - expenses - cost_of_goods,
			uncosted_sales_count=row["uncosted_sales"] or 0,
		)

	@app.get("/insights")
	def business_insights(
		connection: sqlite3.Connection = Depends(get_connection),
	) -> dict[str, object]:
		items = list_inventory(connection)
		low_stock = [item for item in items if item.reorder_level > 0 and item.quantity_on_hand <= item.reorder_level]
		report = profit_report(connection=connection)
		return {
			"period": {"start_date": report.start_date, "end_date": report.end_date},
			"sales_ngn": report.sales_ngn,
			"estimated_profit_ngn": report.estimated_profit_ngn,
			"profit_is_incomplete": report.uncosted_sales_count > 0,
			"uncosted_sales_count": report.uncosted_sales_count,
			"low_stock_items": [item.model_dump() for item in low_stock],
		}

	@app.get("/customers", response_model=list[CustomerBalance])
	def list_customers(
		connection: sqlite3.Connection = Depends(get_connection),
	) -> list[CustomerBalance]:
		rows = connection.execute(
			"""
			SELECT customer AS name,
				   SUM(CASE WHEN type = 'credit_sale' THEN amount_ngn
							WHEN type = 'payment_received' THEN -amount_ngn
							ELSE 0 END) AS balance,
				     COUNT(*) AS entry_count
			FROM entries
			WHERE customer IS NOT NULL
			GROUP BY customer COLLATE NOCASE
			ORDER BY balance DESC, customer COLLATE NOCASE
			"""
		).fetchall()
		customers = []
		for row in rows:
			transactions = connection.execute(
				"""
				SELECT id, type, amount_ngn
				FROM entries
				WHERE customer = ? COLLATE NOCASE
				  AND type IN ('credit_sale', 'payment_received')
				ORDER BY created_at, id
				""",
				(row["name"],),
			).fetchall()
			open_sales: list[list[int]] = []
			for transaction in transactions:
				if transaction["type"] == "credit_sale":
					open_sales.append([transaction["id"], transaction["amount_ngn"]])
					continue
				payment_remaining = transaction["amount_ngn"]
				while payment_remaining and open_sales:
					applied = min(payment_remaining, open_sales[0][1])
					payment_remaining -= applied
					open_sales[0][1] -= applied
					if open_sales[0][1] == 0:
						open_sales.pop(0)

			customers.append(
				CustomerBalance(
					name=row["name"],
					amount_owed_ngn=max(0, row["balance"] or 0),
					open_credit_sales=len(open_sales),
				)
			)
		return customers

	@app.post("/ask")
	def ask(
		request: AskRequest,
		connection: sqlite3.Connection = Depends(get_connection),
	) -> dict[str, object]:
		normalized_question = " ".join(request.question.lower().strip().rstrip("?!.").split())
		if normalized_question not in {"who owes me", "who owes me money"}:
			raise HTTPException(
				status_code=422,
				detail="This backend currently supports 'Who owes me?' only; natural-language query handling is not implemented yet.",
			)

		customers = list_customers(connection)
		owing = [customer for customer in customers if customer.amount_owed_ngn > 0]
		if not owing:
			return {"answer": "Nobody owes you right now.", "customers": []}

		answer = ", ".join(
			f"{customer.name} owes you ₦{customer.amount_owed_ngn:,}" for customer in owing
		)
		return {
			"answer": answer,
			"customers": [customer.model_dump() for customer in owing],
		}

	return app


app = create_app()
