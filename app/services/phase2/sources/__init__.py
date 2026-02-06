"""
Phase 2 Source Plugins
======================
Each module in this package implements a BaseSource subclass
that the SourceManager auto-discovers and orchestrates.

Source tiers:
  S — Breach databases (LeakCheck, Telegram bots) — real leaked data
  A — Platform APIs (VK, GetContact) — direct platform queries
  B — Verification (Holehe, SMTP, Gravatar) — confirms data exists
  C — Pattern generation (email patterns) — educated guessing
"""
