from __future__ import annotations

import httpx


async def send_feishu_webhook_message(webhook_url: str, lines: list[str]) -> None:
    """Send a plain-text message to a Feishu incoming webhook."""
    payload = {
        "msg_type": "text",
        "content": {
            "text": "\n".join(lines),
        },
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(webhook_url, json=payload)
    response.raise_for_status()
