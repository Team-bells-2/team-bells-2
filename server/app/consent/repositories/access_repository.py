from collections.abc import Sequence

from sqlalchemy import select

from app.consent.models import AccessLog, AccessRequest, AccessToken
from app.shared.Infrastructure.db.base_repository import BaseRepository


class AccessRepository(BaseRepository):
    def create_request(self, request: AccessRequest) -> AccessRequest:
        self.db.add(request)
        self.db.flush()
        return request

    def get_request(self, request_id: int) -> AccessRequest | None:
        return self.db.get(AccessRequest, request_id)

    def get_trader_request(self, trader_id: int, request_id: int) -> AccessRequest | None:
        return self.db.scalar(
            select(AccessRequest).where(AccessRequest.id == request_id, AccessRequest.trader_id == trader_id)
        )

    def list_requests(self, trader_id: int, status: str | None) -> Sequence[AccessRequest]:
        query = select(AccessRequest).where(AccessRequest.trader_id == trader_id)
        if status is not None:
            query = query.where(AccessRequest.status == status)
        return self.db.scalars(query.order_by(AccessRequest.requested_at.desc(), AccessRequest.id.desc())).all()

    def get_token_for_request(self, request_id: int) -> AccessToken | None:
        return self.db.scalar(select(AccessToken).where(AccessToken.request_id == request_id))

    def get_token_by_hash(self, token_hash: str) -> AccessToken | None:
        return self.db.scalar(select(AccessToken).where(AccessToken.token_hash == token_hash))

    def create_token(self, token: AccessToken) -> AccessToken:
        self.db.add(token)
        self.db.flush()
        return token

    def add_log(self, request_id: int | None, endpoint: str, result: str) -> AccessLog:
        log = AccessLog(request_id=request_id, endpoint=endpoint, result=result)
        self.db.add(log)
        self.db.flush()
        return log

    def list_logs(self, request_id: int, limit: int) -> Sequence[AccessLog]:
        return self.db.scalars(
            select(AccessLog)
            .where(AccessLog.request_id == request_id)
            .order_by(AccessLog.at.desc(), AccessLog.id.desc())
            .limit(limit)
        ).all()
