"""python-telegram-bot wiring around core.py.

Env: TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID (numeric — the allowlist of one).
Every update from any other user id is dropped and logged, never processed.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import core

log = logging.getLogger("telegram-bridge")

QUEUE_POLL_SECONDS = 5
DIGEST_FLUSH_SECONDS = 30 * 60


class Bridge:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.pending: core.PendingConfirmation | None = None

    def _guard(self, update: Update) -> bool:
        user = update.effective_user
        if user is None or not core.is_owner(user.id):
            log.warning("dropped update from non-owner id %s", user.id if user else None)
            return False
        return True

    async def cmd_status(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if self._guard(update):
            await update.message.reply_text(core.status_text(self.repo_root))

    async def cmd_halt(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if self._guard(update):
            core.halt(self.repo_root, f"telegram /halt msg {update.message.message_id}")
            await update.message.reply_text("KILL file created. All trading halts.")

    async def cmd_resume(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if self._guard(update):
            removed = core.resume(self.repo_root)
            await update.message.reply_text(
                "KILL file removed — trading may resume." if removed else "No KILL file present."
            )

    async def cmd_approve(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._guard(update):
            return
        if not ctx.args:
            await update.message.reply_text("Usage: /approve <promotion-id>")
            return
        try:
            text, pending = core.start_approval(
                self.repo_root, ctx.args[0], update.message.message_id
            )
        except core.ApprovalError as e:
            await update.message.reply_text(str(e))
            return
        self.pending = pending
        await update.message.reply_text(text)

    async def cmd_reject(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._guard(update):
            return
        if not ctx.args:
            await update.message.reply_text("Usage: /reject <promotion-id>")
            return
        try:
            await update.message.reply_text(core.reject_promotion(self.repo_root, ctx.args[0]))
        except core.ApprovalError as e:
            await update.message.reply_text(str(e))

    async def on_text(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._guard(update):
            return
        text = update.message.text or ""
        if self.pending is not None:
            reply = core.confirm_approval(
                self.repo_root, self.pending, text, update.message.message_id
            )
            self.pending = None
            await update.message.reply_text(reply)
            return
        path = core.file_task(self.repo_root, text, update.message.message_id)
        await update.message.reply_text(f"Filed for the orchestrator: {path.name}")

    async def pump_queue(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        """Send high/critical immediately; batch the rest into digests."""
        immediate, batchable = core.scan_queue(self.repo_root)
        chat_id = core.owner_id()
        for event in immediate:
            await ctx.bot.send_message(chat_id, core.format_event(event))
            core.mark_sent(event)

    async def flush_digest(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        _, batchable = core.scan_queue(self.repo_root)
        if not batchable:
            return
        await ctx.bot.send_message(core.owner_id(), core.format_digest(batchable))
        for event in batchable:
            core.mark_sent(event)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    repo_root = core.find_repo_root(Path.cwd())
    bridge = Bridge(repo_root)
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("status", bridge.cmd_status))
    app.add_handler(CommandHandler("halt", bridge.cmd_halt))
    app.add_handler(CommandHandler("resume", bridge.cmd_resume))
    app.add_handler(CommandHandler("approve", bridge.cmd_approve))
    app.add_handler(CommandHandler("reject", bridge.cmd_reject))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bridge.on_text))
    app.job_queue.run_repeating(bridge.pump_queue, interval=QUEUE_POLL_SECONDS, first=5)
    app.job_queue.run_repeating(bridge.flush_digest, interval=DIGEST_FLUSH_SECONDS, first=60)
    log.info("bridge up; owner id %s; repo root %s", core.owner_id(), repo_root)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
