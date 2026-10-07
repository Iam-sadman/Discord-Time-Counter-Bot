# 📚 Discord Time Counter Bot — Cogs Architecture & Documentation Index

This directory contains comprehensive, in-depth architectural and operational documentation for every Cog module in the **Discord Time Counter Bot**.

---

## 🗂️ Cog Modules Directory

| Cog | Source File | Documentation | Key Responsibilities |
|---|---|---|---|
| **VoiceTracking** | [`cogs/voice_tracking.py`](file:///d:/Projects/Discord-Time-Counter-Bot/cogs/voice_tracking.py) | [📖 `voice_tracking.md`](file:///d:/Projects/Discord-Time-Counter-Bot/docs/cogs/voice_tracking.md) | Real-time voice state events, session caching, 60s DB sync, 30s deafen/AFK enforcement, automated monthly reports. |
| **StatsCog** | [`cogs/stats.py`](file:///d:/Projects/Discord-Time-Counter-Bot/cogs/stats.py) | [📖 `stats.md`](file:///d:/Projects/Discord-Time-Counter-Bot/docs/cogs/stats.md) | User voice activity dashboard, audio breakdown (unmuted/muted/deafened), Matplotlib chart generation. |
| **RoleStatsCog** | [`cogs/rolestats.py`](file:///d:/Projects/Discord-Time-Counter-Bot/cogs/rolestats.py) | [📖 `rolestats.md`](file:///d:/Projects/Discord-Time-Counter-Bot/docs/cogs/rolestats.md) | Role-wide member voice auditing, active vs. inactive separation, paginated view, automated CSV export. |
| **ReportCog** | [`cogs/report.py`](file:///d:/Projects/Discord-Time-Counter-Bot/cogs/report.py) | [📖 `report.md`](file:///d:/Projects/Discord-Time-Counter-Bot/docs/cogs/report.md) | Manual server-wide monthly voice activity CSV generation. |
| **LeaderboardCog** | [`cogs/leaderboard.py`](file:///d:/Projects/Discord-Time-Counter-Bot/cogs/leaderboard.py) | [📖 `leaderboard.md`](file:///d:/Projects/Discord-Time-Counter-Bot/docs/cogs/leaderboard.md) | Voice & ECODA leaderboards, bi-monthly cutoff cycles (1st–15th & 16th–End), 3-message live status channel deployment. |
| **EcodaCog** | [`cogs/ecoda.py`](file:///d:/Projects/Discord-Time-Counter-Bot/cogs/ecoda.py) | [📖 `ecoda.md`](file:///d:/Projects/Discord-Time-Counter-Bot/docs/cogs/ecoda.md) | Spreadsheet ingestion (`.csv`/`.xlsx`), team roster autocomplete dropdowns, daily upload status boards, cycle resets. |

---

## 🔗 Shared Utilities Dependency
All cogs interface through [`utils.py`](file:///d:/Projects/Discord-Time-Counter-Bot/utils.py) for:
* SQLite database operations (`voice_activity`, `ecoda_records`, `ecoda_teams`, `ecoda_excluded_workers`, `bot_settings`).
* In-memory session tracking (`active_sessions`, `live_board_state`).
* Formatting functions (`format_duration`, `format_hours`).
* Permissions validation (`is_ecoda_checker`, `can_use_rolestats`).
