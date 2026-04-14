from __future__ import annotations

__all__ = ("execute_tests",)


def __getattr__(name: str):
    if name == "execute_tests":
        from runner.executor import execute_tests

        return execute_tests
    raise AttributeError(name)
