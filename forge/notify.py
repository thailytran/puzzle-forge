"""NotificationPort adapters: Telegram (when configured) else console."""

from __future__ import annotations

import sys
from typing import Any

from forge.config import Settings


class ConsoleNotifier:
    def notify(self, event: str, message: str, data: dict[str, Any] | None = None) -> None:
        print(f"[{event}] {message}", file=sys.stderr)

    def text(self, message: str) -> None:
        self.notify("info", message)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token, self.chat_id = token, chat_id

    def notify(self, event: str, message: str, data: dict[str, Any] | None = None) -> None:
        import httpx

        try:
            httpx.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": f"[{event}] {message}"[:4000]},
                timeout=15,
            )
        except httpx.HTTPError as exc:  # never break a build because a message failed
            print(f"telegram failed: {exc}", file=sys.stderr)

    def text(self, message: str) -> None:
        self.notify("forge", message)


def notifier_from(settings: Settings) -> ConsoleNotifier | TelegramNotifier:
    if settings.telegram_bot_token and settings.telegram_chat_id:
        return TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    return ConsoleNotifier()
