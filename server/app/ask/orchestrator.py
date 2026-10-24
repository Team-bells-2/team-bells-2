from app.ai.orchestrator import AIOrchestrator
from app.ask import services
from app.ask.schemas import AskResponse, OwingCustomer
from app.customers.orchestrator import CustomerOrchestrator
from app.inventory import services as inventory_services
from app.inventory.repositories.inventory_repository import InventoryRepository
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.models import Trader
from app.shared.periods import period_start
from app.suggestions.orchestrator import SuggestionOrchestrator


class AskOrchestrator:
    """POST /ask (FR-S11): pick a whitelisted intent, then answer from the database only."""

    def __init__(
        self,
        customer_orchestrator: CustomerOrchestrator,
        entry_repository: EntryRepository,
        inventory_repository: InventoryRepository,
        suggestion_orchestrator: SuggestionOrchestrator,
        ai_orchestrator: AIOrchestrator,
    ):
        self.customer_orchestrator = customer_orchestrator
        self.entry_repository = entry_repository
        self.inventory_repository = inventory_repository
        self.suggestion_orchestrator = suggestion_orchestrator
        self.ai_orchestrator = ai_orchestrator

    def answer(self, trader: Trader, question: str) -> AskResponse:
        customers = [
            OwingCustomer(name=c.canonical_name, balance_ngn=c.balance_ngn, overdue=c.overdue)
            for c in self.customer_orchestrator.list_trader_customers(trader.id)
        ]
        inventory = {
            item.name: (item, quantity) for item, quantity in self.inventory_repository.list_items_with_quantity(trader.id)
        }
        customer_names, item_names = [c.name for c in customers], list(inventory)

        normalised = services.normalise(question)
        choice = services.keyword_intent(normalised, customer_names, item_names) or self.ai_orchestrator.route_intent(
            question, customer_names, item_names
        )
        if choice is None:
            return AskResponse(intent="unknown", answer=services.FALLBACK_ANSWER)

        if choice.intent == "who_owes":
            owing = sorted((c for c in customers if c.balance_ngn > 0), key=lambda c: -c.balance_ngn)
            return AskResponse(intent="who_owes", answer=services.who_owes_answer(owing), customers=owing)

        if choice.intent == "customer_balance" and choice.customer:
            customer = next(c for c in customers if c.name == choice.customer)
            return AskResponse(
                intent="customer_balance", answer=services.customer_balance_answer(customer), customers=[customer]
            )

        if choice.intent == "today_total":
            sales, _, _ = self.entry_repository.period_totals(trader.id, period_start("today"))
            return AskResponse(intent="today_total", answer=services.today_answer(sales), sales_ngn=sales)

        if choice.intent == "stock_level" and choice.item:
            item, quantity = inventory[choice.item]
            stock = inventory_services.to_item_out(item, quantity)
            answer = services.stock_answer(item.name, stock.quantity_on_hand, item.unit)
            return AskResponse(intent="stock_level", answer=answer, stock=stock)

        if choice.intent == "restock_suggestion" and choice.item:
            return self._restock(trader, choice.item, inventory)

        return AskResponse(intent="unknown", answer=services.FALLBACK_ANSWER)

    def _restock(self, trader: Trader, item_name: str, inventory: dict) -> AskResponse:
        """Same suppliers, same order as GET /suggestions (FR-S32)."""
        stocked = next((item for name, (item, _) in inventory.items() if name.casefold() == item_name.casefold()), None)
        if stocked is None or stocked.reorder_quantity <= 0:
            return AskResponse(intent="restock_suggestion", answer=services.how_many_question(item_name))
        result = self.suggestion_orchestrator.get_suggestions(trader, item_name, stocked.reorder_quantity)
        return AskResponse(
            intent="restock_suggestion",
            answer=services.restock_answer(item_name, result.suggestions),
            suggestions=result,
        )
