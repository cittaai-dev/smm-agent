import httpx
import pytest

from app.tools.web import WebTool


@pytest.mark.asyncio
async def test_fetch_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>ok</html>")

    tool = WebTool()
    tool._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await tool.fetch("https://example.com")
    assert result.status == 200
    assert result.text == "<html>ok</html>"
    assert result.failed_reason is None
    await tool.close()


@pytest.mark.asyncio
async def test_fetch_degrades_on_repeated_failure(monkeypatch):
    import asyncio

    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda *_a, **_kw: real_sleep(0))
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ConnectTimeout("connection timed out")

    tool = WebTool()
    tool._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await tool.fetch("https://unreachable.example.com")
    assert result.status == 0
    assert result.text is None
    assert result.failed_reason is not None
    assert calls["count"] == 3  # initial attempt + 2 retries (webtool_settings.max_retries)
    await tool.close()


@pytest.mark.asyncio
async def test_fetch_recovers_after_transient_failure():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            raise httpx.ConnectTimeout("connection timed out")
        return httpx.Response(200, text="recovered")

    tool = WebTool()
    tool._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await tool.fetch("https://flaky.example.com")
    assert result.status == 200
    assert result.text == "recovered"
    await tool.close()
