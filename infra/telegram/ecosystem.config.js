// PM2 process management for the Telegram control bridge (P6) ONLY.
//
// Deliberately does NOT include the live trading engine (`live/`). Auto-
// restart-on-crash was explicitly declined for that process: if it crashes
// mid-cycle (e.g. because a safety check legitimately halted it), silently
// resuming without a human looking at why would cut against the platform's
// constitution (deliberate human gating for anything that can trade).
// The telegram bridge has no such hazard — it only relays commands/events,
// so unattended auto-restart here is safe.
//
// Usage: see the install/run commands reported alongside this file.

const path = require("path");

const ROOT = __dirname; // infra/telegram/

module.exports = {
  apps: [
    {
      name: "telegram-bridge",
      cwd: ROOT,
      // Runs the installed console script (see pyproject.toml:
      // [project.scripts] telegram-bridge = "telegram_bridge.bot:main")
      // through uv, so it always resolves the project's own venv/lockfile
      // rather than whatever "uv"/"python" happens to be on PATH.
      script: "uv",
      args: "run telegram-bridge",
      interpreter: "none",
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 10,
      min_uptime: "30s",
      error_file: path.join(ROOT, "logs", "error.log"),
      out_file: path.join(ROOT, "logs", "combined.log"),
      merge_logs: true,
      time: true,
    },
  ],
};
