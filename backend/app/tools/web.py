import httpx
from pydantic import BaseModel

from app.infra.settings import webtool_settings


class FetchResult(BaseModel):
    url: str
    status: int
    text: str | None
    failed_reason: str | None = None


class WebTool:
    """The first controlled external-world tool (dual-kb.md's "Live fetch is a
    controlled tool" principle) -- no inline httpx calls scattered through
    ingestion code, everything goes through here. Degrades, never raises
    (P5): a failed fetch is data (FetchResult with failed_reason set), not an
    exception a caller has to remember to catch."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=webtool_settings.timeout_seconds,
                headers={"User-Agent": webtool_settings.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def fetch(self, url: str) -> FetchResult:
        client = self._get_client()
        last_reason = ""
        for attempt in range(webtool_settings.max_retries + 1):
            try:
                resp = await client.get(url)
                return FetchResult(url=url, status=resp.status_code, text=resp.text)
            except httpx.HTTPError as e:
                last_reason = f"{type(e).__name__}: {e}"
                if attempt < webtool_settings.max_retries:
                    import asyncio

                    await asyncio.sleep(min(2**attempt, 4))
        return FetchResult(url=url, status=0, text=None, failed_reason=last_reason)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


_shared_instance: WebTool | None = None


def get_web_tool() -> WebTool:
    global _shared_instance
    if _shared_instance is None:
        _shared_instance = WebTool()
    return _shared_instance
