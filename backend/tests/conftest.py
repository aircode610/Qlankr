import json

import httpx
import pytest

import indexer
from main import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_registry():
    indexer._registry.clear()
    yield
    indexer._registry.clear()


def parse_sse_body(text: str) -> list[dict]:
    """Split SSE text into list of {event, data} dicts."""
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    results = []
    for block in blocks:
        event = "message"
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                raw = line[5:].strip()
                try:
                    data = json.loads(raw)
                except Exception:
                    data = raw
        results.append({"event": event, "data": data})
    return results
