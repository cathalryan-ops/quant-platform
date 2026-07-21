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
        log.info(
            "update %s from user id=%s username=%s",
            update.update_id,
            user.id if user else None,
            user.username if user else None,
        )
        if user is None or not core.is_owner(user.id):
            log.warning(
                "dropped update %s from non-owner id %s (expected %s)",
                update.update_id,
                user.id if user else None,
                core.owner_id(),
            )
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


def _load_env(repo_root: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        log.warning("python-dotenv not installed; .env will not be loaded automatically")
        return
    env_path = repo_root / ".env"
    if not env_path.is_file():
        log.warning("no .env found at %s; relying on process environment only", env_path)
        return
    pre_existing = "TELEGRAM_OWNER_ID" in os.environ
    load_dotenv(env_path, override=False)
    if pre_existing:
        # override=False means .env can NEVER win this — a stray shell/devcontainer
        # export silently shadows any edit made to .env until that process env var
        # itself is unset. This is the most common cause of "I changed .env but
        # nothing changed."
        log.warning(
            "TELEGRAM_OWNER_ID was already set in the process environment "
            "(value=%s) BEFORE .env was loaded — the .env file's value, if "
            "different, is being IGNORED. Unset it in the shell/devcontainer "
            "env or restart the process in a clean environment.",
            os.environ.get("TELEGRAM_OWNER_ID"),
        )
    else:
        log.info("TELEGRAM_OWNER_ID loaded from %s", env_path)


async def _clear_stray_webhook(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    info = await ctx.bot.get_webhook_info()
    if info.url:
        log.warning(
            "a webhook was registered (%s) — this starves run_polling of updates "
            "entirely and silently. Deleting it now.",
            info.url,
        )
        await ctx.bot.delete_webhook(drop_pending_updates=False)
    else:
        log.info("no webhook registered; polling is safe to start")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    repo_root = core.find_repo_root(Path.cwd())
    _load_env(repo_root)  # bot token + owner id from repo-root .env, if present
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
    app.job_queue.run_once(_clear_stray_webhook, when=0)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
