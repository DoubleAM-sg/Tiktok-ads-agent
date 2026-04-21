"""Telegram notification helper — plain-text send to chat/topic."""

from __future__ import annotations

import httpx

from tiktok_ads_agent.core.settings import Settings, load_settings


def send_message(text: str, settings: Settings | None = None) -> None:
    """POST ``text`` to the configured Telegram chat (and topic, if set)."""

    cfg = settings or load_settings()
    body: dict[str, object] = {
        "chat_id": cfg.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if cfg.telegram_topic_id:
        body["message_thread_id"] = int(cfg.telegram_topic_id)

    url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=body)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram sendMessage failed: {payload}")
