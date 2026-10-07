# 🎙️ Discord Time Counter & ECODA Workforce Bot — v3.1

[![Discord.py](https://img.shields.io/badge/discord.py-v2.3+-5865F2.svg?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite%20(aiosqlite)-003B57.svg?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Charts](https://img.shields.io/badge/Visualization-Matplotlib-11557c.svg?logo=python&logoColor=white)](https://matplotlib.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-grade, asynchronous Discord bot engineered with **`discord.py`**, **`aiosqlite`**, and **`matplotlib`**. It provides a unified, dual-engine tracking platform combining **Real-Time Discord Voice Engagement Tracking** and **ECODA Platform Workforce Productivity Management** into a single modular bot.

---

## 📑 Table of Contents

- [🌟 1. System Overview](#-1-system-overview)
- [⚖️ 2. The Verdict: Who Is This Bot For & Who Should Use It?](#️-2-the-verdict-who-is-this-bot-for--who-should-use-it)
- [✨ 3. Core Functionality & Systems](#-3-core-functionality--systems)
  - [System A: Real-Time Discord Voice Tracking & Moderation](#system-a-real-time-discord-voice-tracking--moderation)
  - [System B: ECODA Workforce Activity & Sheet Management](#system-b-ecoda-workforce-activity--sheet-management)
  - [System C: Dedicated Live Dual-Dashboard Channel](#system-c-dedicated-live-dual-dashboard-channel)
  - [System D: Bi-Monthly Cutoff Cycle Engine](#system-d-bi-monthly-cutoff-cycle-engine)
- [🎯 4. Real-World Use Cases](#-4-real-world-use-cases)
- [📋 5. Cog-Wise Slash Command Reference](#-5-cog-wise-slash-command-reference)
  - [📦 Cog 1: `EcodaCog` (`cogs/ecoda.py`)](#-cog-1-ecodacog-cogsecodapy)
  - [📦 Cog 2: `LeaderboardCog` (`cogs/leaderboard.py`)](#-cog-2-leaderboardcog-cogsleaderboardpy)
  - [📦 Cog 3: `StatsCog` (`cogs/stats.py`)](#-cog-3-statscog-cogsstatspy)
  - [📦 Cog 4: `RoleStatsCog` (`cogs/rolestats.py`)](#-cog-4-rolestatscog-cogsrolestatspy)
  - [📦 Cog 5: `ReportCog` (`cogs/report.py`)](#-cog-5-reportcog-cogsreportpy)
  - [📦 Cog 6: `VoiceTrackingCog` (`cogs/voice_tracking.py`)](#-cog-6-voicetrackingcog-cogsvoice_trackingpy)
- [📅 6. Interactive Calendar Date Picker System](#-6-interactive-calendar-date-picker-system)
- [📑 7. Supported Spreadsheet Formats (`.xlsx` / `.csv`)](#-7-supported-spreadsheet-formats-xlsx--csv)
- [🗄️ 8. Database Architecture & Self-Healing Migrations](#️-8-database-architecture--self-healing-migrations)
- [⚙️ 9. Environment Configuration (`.env`)](#️-9-environment-configuration-env)
- [🛠️ 10. Step-by-Step Installation & Deployment Guide](#️-10-step-by-step-installation--deployment-guide)
  - [Method 1: 24/7 Hosting on Ubuntu/Debian VPS with Systemd (Recommended)](#method-1-247-hosting-on-ubuntudebian-vps-with-systemd-recommended)
  - [Method 2: Local Setup (Windows / macOS / Linux)](#method-2-local-setup-windows--macos--linux)
- [🔒 11. Discord Channel & Role Permissions Best Practices](#-11-discord-channel--role-permissions-best-practices)
- [🔄 12. Updating the Bot on VPS](#-12-updating-the-bot-on-vps)
- [❓ 13. Frequently Asked Questions (FAQ)](#-13-frequently-asked-questions-faq)

---

## 🌟 1. System Overview

Remote organizations, business process outsourcing (BPO) firms, and data annotation teams face a common dilemma: **how to maintain operational transparency without micro-management**. Managing distributed workers across different tools requires answering two fundamental questions daily:
1. **Discord Presence & Communication**: Are employees actively collaborating in team voice rooms, or are they muted, deafened, or ghosting their stations?
2. **Platform Productivity (ECODA)**: How many verified billable hours did each worker produce today? Who are our top-performing Labelers? Who are our leading Quality Checkers? And which workers recorded 0 hours and need an attendance check?

**Discord Time Counter Bot v3.1** integrates both worlds into one unified Discord-native interface. Built on an asynchronous foundation (`discord.py` + `aiosqlite`), it operates with zero external database servers, runs 24/7 on minimal resources, and offers persistent UI views with rich pagination, interactive date pickers, and auto-refreshing live dashboard embeds.

```
                           ┌──────────────────────────────────────────────┐
                           │          Discord Gateway Event Stream        │
                           └──────────────┬───────────────────────────────┘
                                          │ on_voice_state_update
                                          ▼
                           ┌──────────────────────────────────────────────┐
                           │       In-Memory State Engine (utils.py)      │
                           │ • active_sessions: {user_id: session_meta}   │
                           │ • deafen_timestamps & afk_moved_timestamps   │
                           └──────────────┬───────────────┬───────────────┘
                                          │               │
                         Periodic Flush   │               │ AFK Loop (30s)
                         (Every 60s)      ▼               ▼
                           ┌──────────────────────────────┐
                           │    SQLite DB (voice_stats.db)│
                           │ ──────────────────────────── │
                           │ • voice_activity (3 states)  │
                           │ • ecoda_records (work hours) │
                           │ • bot_settings (key-values)  │
                           │ • ecoda_blacklist (excluded) │
                           └──────────────┬───────────────┘
                                          │
               ┌──────────────────────────┴──────────────────────────┐
               ▼                                                     ▼
    ┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
    │       Slash Command Engine          │   │      Live Channel Embeds Channel    │
    │ • /stats, /leaderboard              │   │ • 🏆 Live Voice Leaderboard         │
    │ • /rolestats, /report               │   │ • 💼 Live ECODA Leaderboard         │
    │ • /ecoda_upload, /ecoda_add         │   │ (Persistent interactive UI buttons, │
    │ • /ecoda_edit, /ecoda_delete        │   │  paginated, auto-refreshed every    │
    │ • /ecoda_delete_date, /ecoda_reset  │   │  5 minutes and upon sheet upload)   │
    │ • /ecoda_exclude, /cutoff_history   │   │                                     │
    └─────────────────────────────────────┘   └─────────────────────────────────────┘
```

---

## ⚖️ 2. The Verdict: Who Is This Bot For & Who Should Use It?

> ### 📢 The Verdict
> **Discord Time Counter & ECODA Workforce Bot** is built specifically for **data annotation operations, AI training data vendors, BPO agencies, and managed remote teams** that utilize Discord as their central communication hub and manage daily deliverables via production platforms like ECODA.

### 👥 Who Needs This Bot?

1. **AI Data Annotation & Machine Learning Operations**:
   * Agencies that employ dozens or hundreds of remote data labelers and quality checkers.
   * Operations managers who need to import daily CSV/Excel work logs exported from platform portals.
   * Supervisors who must separate **Labeler rankings** from **Checker/QA rankings** to foster healthy competition and assess tier-specific productivity.

2. **BPO, KPO & Remote Outsource Agencies**:
   * Companies where billable hours and team presence must be tracked strictly against payroll cutoff dates.
   * Teams that want to catch non-working personnel immediately via **Inactive (0h)** filters before cutoff closes.

3. **Team Leaders, Checkers & Project Managers**:
   * Team Leads who upload daily work summaries and need instant team attribution (e.g. `Titans`, `Alpha Squad`).
   * Managers who need to audit role-specific voice participation (e.g. `@Annotators`) without manually counting minutes.

4. **Active Communities, Study Rooms & Gaming Guilds**:
   * Communities looking for gamified voice engagement with custom date searches, top medals (`🥇`, `🥈`, `🥉`), and visual charts.

---

## ✨ 3. Core Functionality & Systems

### System A: Real-Time Discord Voice Tracking & Moderation
* **Granular 3-State Tracking**:
  * **🟢 Unmuted**: Actively speaking and listening.
  * **🟡 Muted**: Microphone muted, but listening.
  * **🔴 Deafened**: Audio completely deafened (highest priority state).
* **Automated AFK & Deafen Moderation Engine**:
  * If a user stays **deafened for $\ge 5$ minutes**, the bot automatically moves them to the designated AFK voice channel.
  * If a user lingers in the **AFK channel for $\ge 5$ minutes**, the bot automatically disconnects them from voice.
* **Graphical Charts (`/stats`)**: Dynamically renders an audio distribution donut chart and top 5 channels bar chart via `matplotlib`.
* **Role Auditing (`/rolestats`)**: Audits collective voice time for any server role and generates an attached itemized CSV file.
* **Automated Monthly Archive**: Generates and posts a server-wide voice activity CSV to the private admin channel at `00:00` on the 1st of every month.

### System B: ECODA Workforce Activity & Sheet Management
* **Spreadsheet Ingestion (`/ecoda_upload`)**: Uploads `.csv` or `.xlsx` files with automatic column detection, username resolution, role mapping, and team assignment.
* **Separated Ranking Tiers**:
  * **🏷️ Labelers**: Ranks only data labelers (`role_type = 0`) starting from #1.
  * **🔍 Checkers**: Ranks QA/Checkers (`role_type = 1`) in an independent hierarchy.
* **Active vs. Inactive Workforce Audits**:
  * **`🟢 Active Members`**: Workers with `work_time > 0h` ranked by total logged hours.
  * **`🔴 Inactive (0h)`**: Instantly lists all workers recorded with `0 hours` for the period with their team name for immediate attendance checks.
* **Manual Entry & Corrections (`/ecoda_add`, `/ecoda_edit`)**:
  * Add missed records or adjust hours for any date with custom dates or interactive calendar selection.
* **Multi-Worker Deletion & Date Wiping (`/ecoda_delete`, `/ecoda_delete_date`)**:
  * Remove records for multiple workers simultaneously using comma-separated lists (`e.g. Worker1, Worker2, @User`).
  * Delete records across all dates, today/yesterday, or a specific calendar date.
  * Wipe all uploaded records for a whole date if an incorrect file was uploaded.
* **Safe ECODA Reset (`/ecoda_reset`)**:
  * Wipes all ECODA work records (`ecoda_records`) with a 2-step confirmation prompt.
  * **Voice Data Guarantee**: Discord Voice Activity data is stored in a separate table (`voice_activity`) and remains **100% untouched**.
* **External Worker Blacklist (`/ecoda_exclude`)**:
  * Exclude external or freelance workers from appearing on the leaderboards. Supports adding multiple workers at once.

### System C: Dedicated Live Dual-Dashboard Channel
* Deploys two permanent, self-updating live embeds into a dedicated read-only channel via `/setup_live_leaderboard`:
  1. **🏆 Live Voice Activity Leaderboard**
  2. **💼 Live ECODA Activity Leaderboard**
* **Interactive Persistent Buttons**:
  * **Cutoff Switchers**: `[ ⏳ Current Cutoff ]` and `[ ⏪ Previous Cutoff ]`.
  * **Role Switchers (ECODA)**: `[ 🏷️ Labelers ]`, `[ 🔍 Checkers ]`, `[ 👥 All Roles ]`.
  * **Status Switchers (ECODA)**: `[ 🟢 Active Members ]` and `[ 🔴 Inactive (0h) ]`.
  * **Pagination Controls**: `[ ◀️ Prev ]`, `[ 📄 Page X/Y ]`, `[ Next ▶️ ]`.
  * **Instant Sync**: `[ 🔄 Refresh ]`.

### System D: Bi-Monthly Cutoff Cycle Engine
Workforce productivity is calculated across two official monthly cutoffs:
* **1st Cutoff**: Days `1` to `15` of the month.
* **2nd Cutoff**: Days `16` to the `Last Day` of the month.
* When a cutoff ends, the live leaderboards automatically transition to the new cutoff period.
* Use `/cutoff_history` to inspect any historical cutoff for either Voice or ECODA records.

---

## 🎯 4. Real-World Use Cases

| Scenario | Challenge | How This Bot Solves It |
| :--- | :--- | :--- |
| **Daily Work Sheet Processing** | Team leads get messy CSV exports from portals with hundreds of workers. | Team Lead runs `/ecoda_upload file:today.xlsx team:Titans`. Bot parses roles, auto-links Discord mentions, and updates live leaderboards instantly. |
| **Separating Labelers & Checkers** | Checkers review files faster than labelers create them; combined boards cause friction. | The bot maintains two independent ranking boards. Labelers compete with Labelers; Checkers compete with Checkers. |
| **Auditing Inactive Workers (0h)** | Supervisors spend 30+ minutes cross-checking who was absent or produced 0 hours. | One click on `[ 🔴 Inactive (0h) ]` instantly lists all workers with 0 hours and their team names. |
| **Ghosting in Voice Rooms** | Workers join voice rooms and remain deafened all day to appear active. | The bot flags deafened states, kicks them to AFK after 5 mins, and disconnects them from voice after another 5 mins. |
| **Cutoff Payroll Audits** | Accounts needs final verified hours for Cutoff 1 (1st-15th) on the 16th morning. | Run `/cutoff_history category:ECODA part:1st Cutoff` to get the frozen historical hours. |
| **Fresh Cycle Reset** | Starting a fresh project or billing cycle and wanting to wipe old ECODA sheets. | Run `/ecoda_reset`. Wipes `ecoda_records` cleanly after confirmation while voice records stay 100% safe. |

---

## 📋 Cog-Wise Slash Command Reference

---

### 📦 Cog 1: `EcodaCog` (`cogs/ecoda.py`)
> Handles sheet ingestion, manual hour adjustments, deletions, external worker exclusions, role/channel configuration, and the ECODA reset system.

#### 1. `/ecoda_upload`
* **Purpose:** Uploads a daily ECODA work hours sheet (`.csv` or `.xlsx`). The bot parses worker rows, matches Discord accounts, saves hours, and automatically refreshes all live leaderboards and status boards.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Channel Restriction:** If locked via `/ecoda_set_channel`, can only be run in that designated channel.
* **Parameters:**
  * `file` *(Required, Attachment)*: The `.csv` or `.xlsx` spreadsheet.
  * `team` *(Optional, Autocomplete Dropdown)*: Select from registered teams (e.g. `Delta Force`, `Nano Banana`, `Night Owls`, etc.) with instant searchable autocomplete.
  * `date` *(Optional, String)*: Record date in `YYYY-MM-DD` format (defaults to today).
* **Example:** `/ecoda_upload file:data_oct02.xlsx team:Delta Force`

#### 2. `/ecoda_add`
* **Purpose:** Manually logs or adds missed work hours for a worker without needing to re-upload the entire sheet.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `worker` *(Required, String)*: Discord mention (`@user`) or exact sheet name (e.g. `ARC_Shikto`).
  * `hours` *(Required, Number)*: Hours worked (e.g. `3.5`).
  * `role` *(Optional, Choice)*: `🏷️ Labeler` (`0`, Default) or `🔍 Checker` (`1`).
  * `team` *(Optional, String)*: Optional team name.
  * `date` *(Optional, String)*: Date in `YYYY-MM-DD`. If left empty, opens the **Calendar Date Picker**.
* **Example:** `/ecoda_add worker:@Shikto hours:4.5 role:🏷️ Labeler team:Titans`

#### 3. `/ecoda_edit`
* **Purpose:** Corrects work hours or team name for an existing worker record on a specific date.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `worker` *(Required, String)*: Discord mention or sheet name.
  * `hours` *(Required, Number)*: Corrected work hours (e.g. `2.5` or `0`).
  * `team` *(Optional, String)*: Updated team name.
  * `date` *(Optional, String)*: Date in `YYYY-MM-DD`. If empty, opens the Calendar Date Picker.
  * `note` *(Optional, String)*: Reason or note for this edit.
* **Example:** `/ecoda_edit worker:ARC_Adil hours:0 note:Uploaded duplicate row`

#### 4. `/ecoda_delete`
* **Purpose:** Deletes records for one or multiple workers from the ECODA database.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `workers` *(Required, String)*: Comma-separated names or mentions (e.g. `Rahul, Suman, @Alex`).
  * `date` *(Optional, String)*: Specific date (`YYYY-MM-DD`), `'all'` (removes all records), or leave empty for an interactive choice dialog (`Delete ALL`, `Today`, `Yesterday`, `Calendar`).
* **Example:** `/ecoda_delete workers:WorkerA, WorkerB, @WorkerC date:2026-10-02`

#### 5. `/ecoda_delete_date`
* **Purpose:** Wipes all worker records for an entire specific date (e.g. if a corrupted sheet was uploaded).
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `date` *(Optional, String)*: Target date (`YYYY-MM-DD`). If omitted, opens the Calendar Date Picker.
* **Example:** `/ecoda_delete_date date:2026-10-01`

#### 6. `/ecoda_reset`
* **Purpose:** Completely wipes ALL records from the ECODA database (`ecoda_records`) to allow a fresh start for a new cycle.
* **Safety Mechanism:** Two-step confirmation dialog with `[ ⚠️ Yes, Reset All ECODA Data ]` and `[ ❌ Cancel ]` buttons.
* **Voice Protection:** **Discord Voice Tracking data is 100% preserved and untouched**.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Parameters:** *None.*
* **Example:** `/ecoda_reset`

#### 7. `/ecoda_exclude`
* **Purpose:** Manages the external worker blacklist so non-internal or freelance labelers are hidden from the leaderboard and ignored during daily uploads.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `action` *(Required, Choice)*: `➕ Add to Blacklist`, `➖ Remove from Blacklist`, or `📋 List All Excluded Workers`.
  * `workers` *(Optional, String)*: Comma-separated worker names or mentions.
  * `delete_records` *(Optional, Boolean)*: If `True`, also deletes their historical records.
* **Example:** `/ecoda_exclude action:➕ Add to Blacklist workers:Freelancer1, Freelancer2`

#### 8. `/ecoda_leaderboard`
* **Purpose:** Displays an interactive standalone ECODA leaderboard embed with pagination and dropdown filters.
* **Access Level:** Everyone.
* **Parameters:**
  * `timeframe` *(Optional, Choice)*: Current Cutoff, Previous Cutoff, Today, This Week, This Month, All Time.
  * `role_filter` *(Optional, Choice)*: Labelers Only, Checkers Only, All Roles.
  * `status` *(Optional, Choice)*: Active Members (>0h) or Inactive Members (0h).
* **Example:** `/ecoda_leaderboard timeframe:Current Cutoff role_filter:Labelers Only status:Active Members`

#### 9. `/ecoda_set_role`
* **Purpose:** Configures the Discord role authorized to run ECODA uploads and record modifications.
* **Access Level:** Server Administrator only.
* **Parameters:**
  * `role` *(Required, Role)*: Target role (e.g. `@Team Leader`).
* **Example:** `/ecoda_set_role role:@Team Leader`

#### 10. `/ecoda_set_channel`
* **Purpose:** Restricts `/ecoda_upload` commands to a specific text channel.
* **Access Level:** Server Administrator only.
* **Parameters:**
  * `channel` *(Required, Text Channel)*: Target channel (e.g. `#ecoda-uploads`).
* **Example:** `/ecoda_set_channel channel:#ecoda-uploads`

#### 11. `/ecoda_settings`
* **Purpose:** Shows current configuration (authorized leader role, upload channel, live leaderboards channel).
* **Access Level:** Everyone / Admin.
* **Parameters:** *None.*
* **Example:** `/ecoda_settings`

#### 12. `/ecoda_team` (Command Group)
* **Purpose:** Manages the server's registered team roster used for `/ecoda_upload` autocompletes and daily upload status tracking.
* **Access Level:** Server Administrator only.
* **Subcommands:**
  * `/ecoda_team add name:<str>` — Adds a new team to the active roster.
  * `/ecoda_team remove name:<str>` — Removes a team from the active roster (features autocomplete).
  * `/ecoda_team list` — Displays all registered teams, active status, worker counts, and last activity date.
* **Example:** `/ecoda_team add name:Titans`

#### 13. `/ecoda_team_status`
* **Purpose:** Displays an interactive daily team file upload status dashboard showing which teams have uploaded their sheets and which teams are pending.
* **Access Level:** Team Leader / Checker Role or Server Administrator.
* **Features:**
  * Progress bar with percentage and summary (`✅ 6 Uploaded • ❌ 4 Pending`).
  * 🟢 Uploaded team details (uploader tag, upload time, total workers, work hours).
  * 🔴 Pending team alerts.
  * Interactive navigation buttons: `[ ◀️ Prev Day ]`, `[ 📅 Date Indicator ]`, `[ Next Day ▶️ ]`, `[ 📅 Today ]`, `[ 🔄 Refresh ]`.
* **Parameters:**
  * `date` *(Optional, String)*: Target date in `YYYY-MM-DD` format (defaults to today).
* **Example:** `/ecoda_team_status` or `/ecoda_team_status date:2026-10-02`

---

### 📦 Cog 2: `LeaderboardCog` (`cogs/leaderboard.py`)
> Handles server-wide voice leaderboards, cutoff history exploration, and deployment of the permanent live dynamic leaderboards channel.

#### 14. `/setup_live_leaderboard`
* **Purpose:** Deploys three permanent, self-updating live embeds into a designated channel:
  1. **🏆 Live Voice Activity Leaderboard**
  2. **💼 Live ECODA Activity Leaderboard**
  3. **📊 Live ECODA Team Upload Status Board**
  All three embeds feature persistent interactive buttons (cutoffs, role toggles, active/inactive filters, day navigation, and refresh) that survive bot restarts.
* **Access Level:** Server Administrator only.
* **Parameters:**
  * `channel` *(Required, Text Channel)*: Target channel (e.g. `#leaderboard`).
* **Example:** `/setup_live_leaderboard channel:#leaderboard`

#### 13. `/cutoff_history`
* **Purpose:** Inspects any past or present cutoff leaderboard for either Voice Activity or ECODA Work Hours with pagination support.
* **Access Level:** Everyone.
* **Parameters:**
  * `category` *(Required, Choice)*: `🔊 Voice Activity Leaderboard` or `💼 ECODA Work Hours Leaderboard`.
  * `part` *(Required, Choice)*: `1st Cutoff (1st - 15th)` or `2nd Cutoff (16th - End of Month)`.
  * `month` *(Optional, Integer)*: Month number (`1` to `12`, defaults to current month).
  * `year` *(Optional, Integer)*: Four-digit year (e.g. `2026`, defaults to current year).
* **Example:** `/cutoff_history category:💼 ECODA Work Hours Leaderboard part:1st Cutoff month:9 year:2026`

#### 14. `/leaderboard`
* **Purpose:** Displays the server-wide Discord voice activity leaderboard with dropdown filters for Current Cutoff, Previous Cutoff, Today, This Week, This Month, and All Time.
* **Access Level:** Everyone (Restricted to `STATS_CHANNEL_ID` if configured).
* **Parameters:**
  * `start_date` *(Optional, String)*: Custom start date (`YYYY-MM-DD`).
  * `end_date` *(Optional, String)*: Custom end date (`YYYY-MM-DD`).
* **Example:** `/leaderboard start_date:2026-09-01 end_date:2026-09-15`

---

### 📦 Cog 3: `StatsCog` (`cogs/stats.py`)
> Provides personal and member-specific voice activity visual dashboards.

#### 15. `/stats`
* **Purpose:** Generates an interactive visual voice statistics dashboard for yourself or another user. Renders an audio state donut chart and top 5 channels bar chart via `matplotlib`.
* **Access Level:** Everyone (Restricted to `STATS_CHANNEL_ID` if configured).
* **Parameters:**
  * `user` *(Optional, Member)*: Target user (defaults to command runner).
  * `start_date` *(Optional, String)*: Custom start date (`YYYY-MM-DD`).
  * `end_date` *(Optional, String)*: Custom end date (`YYYY-MM-DD`).
* **Example:** `/stats user:@Alex start_date:2026-09-01 end_date:2026-09-15`

---

### 📦 Cog 4: `RoleStatsCog` (`cogs/rolestats.py`)
> Provides administrative voice participation audits for entire Discord server roles.

#### 16. `/rolestats`
* **Purpose:** Audits the collective and individual voice time of all members possessing a specific server role. Features interactive active/inactive member filters and automatically generates an itemized CSV spreadsheet attachment.
* **Access Level:** Server Administrator or roles specified in `ROLESTATS_ALLOWED_ROLES`.
* **Parameters:**
  * `role` *(Required, Role)*: Target role (e.g. `@Annotators`).
  * `start_date` *(Optional, String)*: Start date (`YYYY-MM-DD`).
  * `end_date` *(Optional, String)*: End date (`YYYY-MM-DD`).
* **Example:** `/rolestats role:@Annotators start_date:2026-10-01 end_date:2026-10-15`

---

### 📦 Cog 5: `ReportCog` (`cogs/report.py`)
> Generates manual monthly export reports.

#### 17. `/report`
* **Purpose:** Manually exports and posts a comprehensive CSV spreadsheet containing every member's voice activity breakdown for the current month.
* **Access Level:** Everyone (Restricted to `STATS_CHANNEL_ID` if configured).
* **Parameters:** *None.*
* **Example:** `/report`

---

### 📦 Cog 6: `VoiceTrackingCog` (`cogs/voice_tracking.py`)
> The real-time engine of the bot. Contains no slash commands, but powers all voice logging and automation loops.

* **Gateway Listener (`on_voice_state_update`)**: Tracks member connects, disconnects, deafens, and mutes in memory.
* **Periodic Sync Loop (`flush_voice_activity`)**: Flushes all active in-memory voice sessions to SQLite every 60 seconds.
* **AFK Moderation Loop (`check_afk_and_deafened`)**: Runs every 30 seconds. Enforces 5-minute deafen-to-AFK moves and 5-minute AFK-to-disconnect kicks.
* **Monthly Report Task**: Automatically fires on the 1st of every month at `00:00` local time, generating and delivering a complete voice activity CSV to `REPORT_CHANNEL_ID`.

---

## 📅 6. Interactive Calendar Date Picker System

Whenever a date parameter is left blank in `/ecoda_add`, `/ecoda_edit`, `/ecoda_delete`, or `/ecoda_delete_date`, the bot launches an **Interactive Discord Calendar View**:

```
┌──────────────────────────────────────────────────────────┐
│  📅 Select Date for Record                               │
│  [ ☀️ Today ]   [ ⏪ Yesterday ]   [ ❌ Cancel ]         │
│                                                          │
│  Select Cutoff Date:                                     │
│  [ ⏳ Current Cutoff (Oct 1 - Oct 15) ▼ ]                │
│                                                          │
│  Or Browse Full Calendar:                                │
│  [ ◀️ Prev Month ]   [ October 2026 ]   [ Next Month ▶️ ] │
│  [ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ] [ 6 ] [ 7 ]               │
│  [ 8 ] [ 9 ] [ 10 ] [ 11 ] [ 12 ] [ 13 ] [ 14 ] [ 15 ]   │
└──────────────────────────────────────────────────────────┘
```

1. **Quick Buttons**: One-click selection for **Today** and **Yesterday**.
2. **Cutoff Dropdown**: Instantly pick any valid date within the active cutoff.
3. **Month Grid**: Navigate forward or backward across months to pick historical dates.

---

## 📑 7. Supported Spreadsheet Formats (`.xlsx` / `.csv`)

The parser accepts both Excel `.xlsx` and comma-separated `.csv` files. It automatically normalizes headers and handles various column aliases.

### Column Mapping Reference:
| Standard Header | Supported Aliases | Required? | Purpose |
| :--- | :--- | :---: | :--- |
| `user_name` | `username`, `worker_name`, `name`, `ecoda_name` | **Yes** | Worker's sheet name (e.g. `ARC_Shikto Kumar Das`) |
| `default_role` | `role`, `role_type` | **Yes** | `0` for **Labeler**, `1` for **Checker** |
| `work_time` | `work_hour`, `hours`, `time` | **Yes** | Decimal hours worked (e.g. `2.5`, `1.578`, `0`) |
| `group_id` | `group` | *No* | Department or Project numerical ID (e.g. `901`) |
| `team_id` | `team` (numeric) | *No* | Numeric team identifier (e.g. `202`) |
| `team_name` | `team` (text), `team_title` | *No* | Team name string (e.g. `Titans`). Applied from `/ecoda_upload team:...` if omitted in the sheet. |

### Sample CSV File:
```csv
user_name,default_role,work_time,group_id,team_id
ARC_Nasar Ahmed Hridoy,0,0,901,202
ARC_Shikto Kumar Das,0,1.578,901,202
ARC_Sadman Sakib,1,3.250,901,202
ARC_Adil Arham,0,0,901,202
```

---

## 🗄️ 8. Database Architecture & Self-Healing Migrations

The database is built on **SQLite** (`voice_stats.db`) using `aiosqlite`. It requires zero external database servers (like MySQL or PostgreSQL), ensuring complete independence and zero latency.

```sql
-- 1. Voice Tracking Table (Aggregated daily per user and channel)
CREATE TABLE IF NOT EXISTS voice_activity (
    user_id INTEGER,
    user_name TEXT,
    channel_id INTEGER,
    channel_name TEXT,
    record_date TEXT,
    unmuted_seconds REAL DEFAULT 0,
    muted_seconds REAL DEFAULT 0,
    deafened_seconds REAL DEFAULT 0,
    PRIMARY KEY (user_id, channel_id, record_date)
);

-- 2. ECODA Workforce Records Table
CREATE TABLE IF NOT EXISTS ecoda_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    ecoda_name TEXT NOT NULL,
    role_type INTEGER DEFAULT 0,
    work_time REAL DEFAULT 0,
    group_id INTEGER,
    team_id INTEGER,
    team_name TEXT,
    record_date TEXT NOT NULL,
    uploaded_by INTEGER,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ecoda_name, record_date) ON CONFLICT REPLACE
);

-- 3. In-Server Dynamic Settings Table
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 4. External Workers Blacklist Table
CREATE TABLE IF NOT EXISTS ecoda_blacklist (
    ecoda_name TEXT PRIMARY KEY,
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Self-Healing Auto-Migrations:
Upon every bot startup (`init_db()`), the bot checks existing database columns using `PRAGMA table_info`. If a newer column (like `team_name`) does not exist in your existing database file, the bot dynamically executes:
```sql
ALTER TABLE ecoda_records ADD COLUMN team_name TEXT;
```
Existing voice tracking and workforce records are **100% preserved**.

---

## ⚙️ 9. Environment Configuration (`.env`)

Create a `.env` file in the root folder of the bot based on `.env.example`:

```env
# ==============================================================================
# DISCORD BOT TOKEN (Required)
# ==============================================================================
BOT_TOKEN=your_bot_token_here

# ==============================================================================
# CHANNEL RESTRICTIONS & LOGGING (Optional - leave blank if not restricted)
# ==============================================================================
# Private text channel ID where automated monthly CSV reports are sent on the 1st
REPORT_CHANNEL_ID=1473963048028082227

# Text channel ID to restrict /stats, /leaderboard, and /report commands
STATS_CHANNEL_ID=1550433774972698674

# Voice channel ID where users deafened >= 5 mins are moved
AFK_CHANNEL_ID=1473963047532892262

# ==============================================================================
# ROLE PERMISSIONS (Optional)
# ==============================================================================
# Comma-separated Role IDs or Role Names authorized to run /rolestats
ROLESTATS_ALLOWED_ROLES=1473963046396494021,1474690818387349514

# ==============================================================================
# LOCAL TIMEZONE (Required for Cutoff accuracy)
# ==============================================================================
TIMEZONE=Asia/Dhaka

# ==============================================================================
# SQLITE DATABASE STORAGE (Optional - defaults to voice_stats.db)
# ==============================================================================
DB_FILE=voice_stats.db
```

---

## 🛠️ 10. Step-by-Step Installation & Deployment Guide

### Method 1: 24/7 Hosting on Ubuntu/Debian VPS with Systemd (Recommended)

#### Step 1: Update Server Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git curl -y
```

#### Step 2: Clone Repository
```bash
cd ~
git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
cd Discord-Time-Counter-Bot
```

#### Step 3: Create Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Configure `.env`
```bash
cp .env.example .env
nano .env
```
*(Paste your `BOT_TOKEN`, set `TIMEZONE=Asia/Dhaka`, configure channel IDs, save with `Ctrl+O`, `Enter`, and exit with `Ctrl+X`)*

#### Step 5: Configure 24/7 Systemd Background Service
Create the service unit file:
```bash
sudo nano /etc/systemd/system/counterbot.service
```

Paste the following configuration (replace `ubuntu` with your Linux username if different):
```ini
[Unit]
Description=Discord Time Counter & ECODA Workforce Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Discord-Time-Counter-Bot
ExecStart=/home/ubuntu/Discord-Time-Counter-Bot/.venv/bin/python /home/ubuntu/Discord-Time-Counter-Bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Step 6: Enable and Start the Bot
```bash
sudo systemctl daemon-reload
sudo systemctl enable counterbot.service
sudo systemctl start counterbot.service
```

#### Step 7: Check Service Health & Logs
```bash
# Verify active status
sudo systemctl status counterbot.service

# Stream live console logs
sudo journalctl -u counterbot.service -f
```

---

### Method 2: Local Setup (Windows / macOS / Linux)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
   cd Discord-Time-Counter-Bot
   ```
2. **Create and activate virtual environment**:
   * **Windows**:
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```
   * **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Set up `.env`**:
   ```bash
   copy .env.example .env   # Windows
   cp .env.example .env     # Linux / macOS
   ```
   *(Edit `.env` with your token and timezone)*
5. **Run the bot**:
   ```bash
   python bot.py
   ```

---

## 🔒 11. Discord Channel & Role Permissions Best Practices

### For `#leaderboard` (Live Dynamic Boards Channel):
1. Run `/setup_live_leaderboard channel:#leaderboard`.
2. Go to **Discord Channel Settings** ➔ **Permissions** ➔ **`@everyone`**:
   * **View Channel**: ✅ `Allow`
   * **Read Message History**: ✅ `Allow`
   * **Send Messages**: ❌ `Deny`
   * **Add Reactions**: ❌ `Deny`
3. Ensure the bot's role has:
   * **View Channel**: ✅ `Allow`
   * **Send Messages**: ✅ `Allow`
   * **Embed Links**: ✅ `Allow`
   * **Manage Messages**: ✅ `Allow`

*This guarantees that chat messages won't drown out the live boards while every user can freely interact with the buttons.*

### For `#ecoda-uploads` (Upload Channel):
1. Lock uploads to this channel: `/ecoda_set_channel channel:#ecoda-uploads`.
2. Restrict access: Set `/ecoda_set_role role:@Team Leader`.
3. Only Team Leaders and Admins will be permitted to upload files, preventing general chat disruption.

---

## 🔄 12. Updating the Bot on VPS

Whenever new updates are pushed to the GitHub repository:

```bash
cd ~/Discord-Time-Counter-Bot

# 1. Pull latest commits from GitHub
git pull origin main

# 2. Restart the systemd service
sudo systemctl restart counterbot.service

# 3. Check logs to confirm clean startup
sudo journalctl -u counterbot.service -n 20 --no-pager
```

---

## ❓ 13. Frequently Asked Questions (FAQ)

#### Q1: Does running `/ecoda_reset` wipe our Discord Voice Activity data?
**A:** **No, absolutely not.** Voice tracking and ECODA work hours are completely decoupled in separate SQLite tables (`voice_activity` vs. `ecoda_records`). Running `/ecoda_reset` executes `DELETE FROM ecoda_records` only. Your voice minutes, channel breakdowns, and user activity remain 100% safe and intact.

#### Q2: What happens if an employee changes their Discord nickname?
**A:** The bot resolves worker names dynamically on every database sync. As soon as a worker updates their Discord server nickname to match their sheet name, the bot immediately links their Discord account (`<@user_id>`) across all live embeds and leaderboards.

#### Q3: Can Team Leaders upload files from any channel?
**A:** By default, yes. However, an Administrator can lock uploads to a specific channel using `/ecoda_set_channel`. Once locked, any upload attempt in another channel is rejected with an ephemeral notification directing the user to the designated channel.

#### Q4: How do supervisors check who logged 0 hours for attendance?
**A:** In the Live ECODA Leaderboard channel, simply click the **`[ 🔴 Inactive (0h) ]`** button. The embed instantly refreshes to list every worker recorded with 0 hours alongside their team name for that cutoff period.

#### Q5: Can I delete or blacklist multiple workers at once?
**A:** Yes. Both `/ecoda_delete` and `/ecoda_exclude` support comma-separated values (e.g. `workers:Worker1, Worker2, @Worker3`).

---

## 📜 License

Distributed under the **MIT License**. You are free to modify, deploy, and distribute this project for commercial and personal operations.