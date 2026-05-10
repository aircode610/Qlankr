import os
from functools import lru_cache
from uuid import UUID

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


class _ScopedQuery:
    def __init__(self, client, table: str, user_id: UUID, op: str, payload=None):
        self._client = client
        self._table = table
        self._user_id = str(user_id)
        self._op = op
        self._payload = payload
        self._extra_filters: list[tuple[str, object]] = []
        self._order: tuple | None = None
        self._limit: int | None = None

    def eq(self, column: str, value):
        self._extra_filters.append((column, value))
        return self

    def order(self, *args, **kwargs):
        self._order = (args, kwargs)
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def execute(self):
        tbl = self._client.table(self._table)
        if self._op == "select":
            q = tbl.select(*(self._payload or ["*"])).eq("user_id", self._user_id)
            for c, v in self._extra_filters:
                q = q.eq(c, v)
            if self._order:
                q = q.order(*self._order[0], **self._order[1])
            if self._limit is not None:
                q = q.limit(self._limit)
            return q.execute()
        if self._op == "insert":
            row = {**self._payload, "user_id": self._user_id}
            return tbl.insert(row).execute()
        if self._op == "update":
            q = tbl.update(self._payload).eq("user_id", self._user_id)
            for c, v in self._extra_filters:
                q = q.eq(c, v)
            return q.execute()
        if self._op == "delete":
            q = tbl.delete().eq("user_id", self._user_id)
            for c, v in self._extra_filters:
                q = q.eq(c, v)
            return q.execute()
        if self._op == "upsert":
            row = {**self._payload, "user_id": self._user_id}
            return tbl.upsert(row).execute()
        raise NotImplementedError(self._op)


class _ScopedTable:
    def __init__(self, client, table: str, user_id: UUID):
        self._client = client
        self._table = table
        self._user_id = user_id

    def select(self, *columns) -> _ScopedQuery:
        return _ScopedQuery(self._client, self._table, self._user_id, "select", list(columns) or ["*"])

    def insert(self, payload: dict) -> _ScopedQuery:
        return _ScopedQuery(self._client, self._table, self._user_id, "insert", payload)

    def update(self, payload: dict) -> _ScopedQuery:
        """Update rows matching `user_id`. ALWAYS chain `.eq(...)` with a row-identifying
        filter — without it, every row the user owns in this table is updated. The service
        role bypasses RLS, so this wrapper is the only guard against table-wide mutations."""
        return _ScopedQuery(self._client, self._table, self._user_id, "update", payload)

    def delete(self) -> _ScopedQuery:
        """Delete rows matching `user_id`. ALWAYS chain `.eq(...)` with a row-identifying
        filter — without it, every row the user owns in this table is deleted."""
        return _ScopedQuery(self._client, self._table, self._user_id, "delete")

    def upsert(self, payload: dict) -> _ScopedQuery:
        return _ScopedQuery(self._client, self._table, self._user_id, "upsert", payload)


class UserScoped:
    """All operations filter and inject user_id automatically."""

    def __init__(self, client, user_id: UUID):
        self._client = client
        self._user_id = user_id

    def table(self, name: str) -> _ScopedTable:
        return _ScopedTable(self._client, name, self._user_id)


def user_scoped(user_id: UUID) -> UserScoped:
    return UserScoped(get_client(), user_id)
