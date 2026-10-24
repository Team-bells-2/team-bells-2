from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.consent import services
from app.consent.models import AccessLog, AccessRequest, AccessToken
from app.consent.repositories.access_repository import AccessRepository
from app.consent.schemas import (
    AccessLogOut,
    AccessRequestCreate,
    AccessRequestCreated,
    AccessRequestOut,
    AccessRequestStatus,
    AgentSummary,
)
from app.ledger.repositories.entry_repository import EntryRepository
from app.onboarding.repositories.trader_repository import TraderRepository
from app.shared.errors import AppError
from app.shared.Infrastructure.realtime.hub import EventPublisher


class ConsentOrchestrator:
    """Consent-gated agent access (FR-S13 to S17). The agent names the trader by phone, polls with a
    claim secret, and collects its token exactly once after the trader approves (BR-K1 to K8).
    """

    def __init__(
        self,
        access_repository: AccessRepository,
        trader_repository: TraderRepository,
        entry_repository: EntryRepository,
        token_ttl_minutes: int,
        events: EventPublisher,
    ):
        self.access_repository = access_repository
        self.trader_repository = trader_repository
        self.entry_repository = entry_repository
        self.token_ttl_minutes = token_ttl_minutes
        self.events = events

    # --- agent side ---------------------------------------------------------------------------

    def create_request(self, request: AccessRequestCreate) -> AccessRequestCreated:
        """Open endpoint; returns no business data, only a secret to poll with (BR-K1)."""
        trader = self.trader_repository.get_trader_by_phone(request.trader_phone)
        if trader is None:
            raise AppError(404, "trader_not_found", "No trader uses that phone number.")
        claim_secret = services.new_secret()
        try:
            access = self.access_repository.create_request(
                AccessRequest(
                    trader_id=trader.id,
                    agent_name=request.agent_name,
                    purpose=request.purpose,
                    scopes=list(request.data_scopes),
                    claim_hash=services.hash_secret(claim_secret),
                )
            )
            log = self.access_repository.add_log(
                access.id, "POST /access-requests", "requested"
            )
            self.access_repository.commit()
        except Exception:
            self.access_repository.rollback()
            raise
        self.events.publish(
            trader.id,
            "access_requested",
            {
                "id": access.id,
                "agent_name": access.agent_name,
                "purpose": access.purpose,
                "scopes": access.scopes,
                "status": access.status,
            },
        )
        self._publish_access_log(trader.id, log)
        return AccessRequestCreated(
            request_id=access.id, status="pending", claim_secret=claim_secret
        )

    def request_status(self, request_id: int, claim_secret: str) -> AccessRequestStatus:
        """The agent polls; after approval the token is returned exactly once (BR-K2)."""
        access = self.access_repository.get_request(request_id)
        if access is None or not services.secrets_match(
            access.claim_hash, claim_secret
        ):
            raise AppError(404, "request_not_found", "Access request not found.")
        status = AccessRequestStatus(
            request_id=access.id,
            status=access.status,  # pyright: ignore[reportArgumentType]  (DB check constraint)
            scopes=access.scopes,
        )
        if access.status != "approved" or access.expires_at is None:
            return status

        issued = self.access_repository.get_token_for_request(access.id)
        if issued is not None:
            return status.model_copy(
                update={
                    "token_already_collected": True,
                    "expires_at": services.as_utc(issued.expires_at),
                }
            )
        token = services.new_secret()
        try:
            self.access_repository.create_token(
                AccessToken(
                    request_id=access.id,
                    token_hash=services.hash_secret(token),
                    expires_at=access.expires_at,
                )
            )
            log = self.access_repository.add_log(
                access.id, "GET /access-requests/{id}/status", "token_issued"
            )
            self.access_repository.commit()
        except Exception:
            self.access_repository.rollback()
            raise
        self._publish_access_log(access.trader_id, log)
        return status.model_copy(
            update={
                "access_token": token,
                "token_type": "bearer",
                "expires_at": services.as_utc(access.expires_at),
            }
        )

    def agent_summary(self, token: str | None) -> AgentSummary:
        """Totals only, for the approved scopes (FR-S15). Every call is logged (FR-S16, BR-K7)."""
        endpoint = "GET /agent/summary"
        if not token:
            self._log_and_fail(
                None, endpoint, 401, "missing_token", "Bearer access token required."
            )
        stored = self.access_repository.get_token_by_hash(
            services.hash_secret(token or "")
        )
        access = (
            self.access_repository.get_request(stored.request_id) if stored else None
        )
        if stored is None or access is None:
            self._log_and_fail(
                None, endpoint, 401, "invalid_token", "Access token is not valid."
            )
        assert stored is not None and access is not None
        now = datetime.now(UTC)
        if stored.revoked_at is not None or access.status == "revoked":
            self._log_and_fail(
                access.id,
                endpoint,
                403,
                "revoked",
                "The trader revoked this access.",
                access.trader_id,
            )
        if services.as_utc(stored.expires_at) <= now:
            self._log_and_fail(
                access.id,
                endpoint,
                401,
                "expired",
                "This access token has expired.",
                access.trader_id,
            )

        since = now - timedelta(days=services.SUMMARY_PERIOD_DAYS)
        summary = AgentSummary(
            period_days=services.SUMMARY_PERIOD_DAYS,
            generated_at=now,
            scopes=access.scopes,  # pyright: ignore[reportArgumentType]
        )
        if "sales_total" in access.scopes:
            summary.sales_total_ngn, _, _ = self.entry_repository.period_totals(
                access.trader_id, since
            )
        if "active_days" in access.scopes:
            summary.active_days = services.active_days(
                self.entry_repository.entry_times(access.trader_id, since)
            )
        if "total_owed" in access.scopes:
            summary.total_owed_ngn = services.total_owed(
                self.entry_repository.customer_balances(access.trader_id).values()
            )
        try:
            log = self.access_repository.add_log(access.id, endpoint, "ok")
            self.access_repository.commit()
        except Exception:
            self.access_repository.rollback()
            raise
        self._publish_access_log(access.trader_id, log)
        return summary

    # --- trader side --------------------------------------------------------------------------

    def list_requests(
        self, trader_id: int, status: str | None
    ) -> list[AccessRequestOut]:
        return [
            self._request_out(access)
            for access in self.access_repository.list_requests(trader_id, status)
        ]

    def decide(
        self, trader_id: int, request_id: int, approve: bool
    ) -> AccessRequestOut:
        """Approve or reject a pending request; approval sets the token expiry (FR-S14, BR-K3)."""
        access = self._trader_request(trader_id, request_id)
        if access.status != "pending":
            raise AppError(
                409, "already_decided", f"This request is already {access.status}."
            )
        now = datetime.now(UTC)
        try:
            access.status = "approved" if approve else "rejected"
            access.decided_at = now
            if approve:
                access.expires_at = now + timedelta(minutes=self.token_ttl_minutes)
            log = self.access_repository.add_log(
                access.id, "POST /access-requests/{id}/approve", access.status
            )
            self.access_repository.commit()
        except Exception:
            self.access_repository.rollback()
            raise
        self.events.publish(
            trader_id,
            "access_decided",
            {"id": access.id, "status": access.status, "scopes": access.scopes},
        )
        self._publish_access_log(trader_id, log)
        return self._request_out(access)

    def revoke(self, trader_id: int, request_id: int) -> AccessRequestOut:
        """Immediate: the next summary call with its token returns 403 (FR-S17, BR-K5)."""
        access = self._trader_request(trader_id, request_id)
        try:
            access.status = "revoked"
            token = self.access_repository.get_token_for_request(access.id)
            if token is not None and token.revoked_at is None:
                token.revoked_at = datetime.now(UTC)
            log = self.access_repository.add_log(access.id, "DELETE /access/{id}", "revoked")
            self.access_repository.commit()
        except Exception:
            self.access_repository.rollback()
            raise
        self.events.publish(
            trader_id,
            "access_revoked",
            {"id": access.id, "status": access.status},
        )
        self._publish_access_log(trader_id, log)
        return self._request_out(access)

    # --- helpers ------------------------------------------------------------------------------

    def _trader_request(self, trader_id: int, request_id: int) -> AccessRequest:
        access = self.access_repository.get_trader_request(trader_id, request_id)
        if access is None:
            raise AppError(404, "request_not_found", "Access request not found.")
        return access

    def _request_out(self, access: AccessRequest) -> AccessRequestOut:
        logs: Sequence[AccessLog] = self.access_repository.list_logs(
            access.id, services.LOG_ROWS_SHOWN
        )
        return AccessRequestOut(
            id=access.id,
            agent_name=access.agent_name,
            purpose=access.purpose,
            scopes=access.scopes,  # pyright: ignore[reportArgumentType]
            status=access.status,  # pyright: ignore[reportArgumentType]
            requested_at=services.as_utc(access.requested_at),
            decided_at=(
                services.as_utc(access.decided_at) if access.decided_at else None
            ),
            expires_at=(
                services.as_utc(access.expires_at) if access.expires_at else None
            ),
            prompt=services.consent_prompt(
                access.agent_name, access.scopes, self.token_ttl_minutes
            ),
            log=[
                AccessLogOut(
                    endpoint=row.endpoint, result=row.result, at=services.as_utc(row.at)
                )
                for row in logs
            ],
        )

    def _log_and_fail(
        self,
        request_id: int | None,
        endpoint: str,
        status: int,
        code: str,
        message: str,
        trader_id: int | None = None,
    ) -> None:
        """Failed agent calls are logged too (FR-S16), so the log row commits before the error."""
        try:
            log = self.access_repository.add_log(request_id, endpoint, code)
            self.access_repository.commit()
        except Exception:
            self.access_repository.rollback()
            raise
        if trader_id is not None:
            self._publish_access_log(trader_id, log)
        raise AppError(status, code, message)

    def _publish_access_log(self, trader_id: int, log: AccessLog) -> None:
        self.events.publish(
            trader_id,
            "access_log",
            {
                "request_id": log.request_id,
                "endpoint": log.endpoint,
                "result": log.result,
                "at": services.as_utc(log.at),
            },
        )
