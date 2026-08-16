from dataclasses import dataclass

import httpx

from app.config import settings


@dataclass
class SendResult:
    ok: bool
    status_code: int
    dm_id: str | None = None
    api_status: str | None = None
    retry_after: float | None = None
    error: str | None = None
    retryable: bool = True


class PseudoGramClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.pseudogram_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.pseudogram_api_key
        self._client = httpx.AsyncClient(timeout=20.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def send_dm(
        self,
        recipient_user_id: str,
        message: str,
        comment_id: str,
        idempotency_key: str,
    ) -> SendResult:
        url = f"{self.base_url}/v1/dm/send"
        try:
            response = await self._client.post(
                url,
                headers=self._headers(idempotency_key),
                json={
                    "recipient_user_id": recipient_user_id,
                    "message": message,
                    "comment_id": comment_id,
                },
            )
        except httpx.HTTPError as exc:
            return SendResult(ok=False, status_code=0, error=str(exc), retryable=True)

        if response.status_code == 202:
            body = response.json()
            return SendResult(
                ok=True,
                status_code=202,
                dm_id=body.get("dm_id"),
                api_status=body.get("status"),
            )

        retry_after = None
        if "Retry-After" in response.headers:
            try:
                retry_after = float(response.headers["Retry-After"])
            except ValueError:
                retry_after = 5.0

        error_text = response.text
        try:
            error_text = response.json().get("error") or response.text
        except Exception:
            pass

        if response.status_code == 429:
            return SendResult(
                ok=False,
                status_code=429,
                error="rate_limited",
                retry_after=retry_after or 5.0,
                retryable=True,
            )
        if response.status_code == 500:
            return SendResult(ok=False, status_code=500, error=error_text, retryable=True)
        if response.status_code == 400:
            return SendResult(ok=False, status_code=400, error=error_text, retryable=False)
        return SendResult(ok=False, status_code=response.status_code, error=error_text, retryable=True)

    async def get_dm(self, dm_id: str) -> dict | None:
        url = f"{self.base_url}/v1/dm/{dm_id}"
        try:
            response = await self._client.get(url, headers=self._headers())
            if response.status_code != 200:
                return None
            return response.json()
        except httpx.HTTPError:
            return None
