"""Telegram bridge (P6): the human control plane.

Inbound: /status, /halt, /resume, /approve, /reject, free text -> task queue.
Outbound: events.schema.json instances from the file queue; info/warning
batched into digests, high/critical sent immediately.
"""
