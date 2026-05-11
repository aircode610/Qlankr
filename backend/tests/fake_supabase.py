"""In-memory fake of the supabase-py client surface we use.

Only the parts of the `.table(...).select/insert/update/delete/eq/execute()`
chain that this codebase touches are implemented. Add more as needed.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any


class _Query:
    def __init__(self, store: dict, table: str, op: str, payload: Any = None):
        self._store = store
        self._table = table
        self._op = op
        self._payload = payload
        self._filters: list[tuple[str, Any]] = []

    def eq(self, column: str, value: Any) -> "_Query":
        self._filters.append((column, value))
        return self

    def order(self, *_args, **_kwargs) -> "_Query":
        return self

    def limit(self, *_args) -> "_Query":
        return self

    def execute(self):
        rows = self._store.setdefault(self._table, [])
        if self._op == "select":
            matched = [r for r in rows if self._matches(r)]
            return _Response(matched)
        if self._op == "insert":
            payload = copy.deepcopy(self._payload)
            if isinstance(payload, list):
                for row in payload:
                    row.setdefault("id", str(uuid.uuid4()))
                rows.extend(payload)
                return _Response(payload)
            payload.setdefault("id", str(uuid.uuid4()))
            rows.append(payload)
            return _Response([payload])
        if self._op == "update":
            updated = []
            for row in rows:
                if self._matches(row):
                    row.update(self._payload)
                    updated.append(row)
            return _Response(updated)
        if self._op == "delete":
            removed = [r for r in rows if self._matches(r)]
            self._store[self._table] = [r for r in rows if not self._matches(r)]
            return _Response(removed)
        raise NotImplementedError(self._op)

    def _matches(self, row: dict) -> bool:
        return all(row.get(c) == v for c, v in self._filters)


class _Response:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, store: dict, name: str):
        self._store = store
        self._name = name

    def select(self, *_args, **_kwargs) -> _Query:
        return _Query(self._store, self._name, "select")

    def insert(self, payload) -> _Query:
        return _Query(self._store, self._name, "insert", payload)

    def update(self, payload) -> _Query:
        return _Query(self._store, self._name, "update", payload)

    def delete(self) -> _Query:
        return _Query(self._store, self._name, "delete")

    def upsert(self, payload) -> _Query:
        # Treat upsert as insert-or-update keyed by primary key (id or user_id).
        key = "user_id" if "user_id" in payload else "id"
        existing = self._store.setdefault(self._name, [])
        match = next((r for r in existing if r.get(key) == payload.get(key)), None)
        if match:
            match.update(payload)
            return _Query(self._store, self._name, "select")  # noop-ish
        return self.insert(payload)


class FakeSupabaseClient:
    def __init__(self):
        self._store: dict = {}

    def table(self, name: str) -> _Table:
        return _Table(self._store, name)

    def reset(self):
        self._store.clear()
