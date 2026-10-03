# 🎙️ Discord Time Counter & ECODA Workforce Bot — v3.1

[![Discord.py](https://img.shields.io/badge/discord.py-v2.3+-5865F2.svg?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite%20(aiosqlite)-003B57.svg?logo=sqlite&logoColor=white)](https://sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An enterprise-grade, asynchronous Discord bot designed for **remote teams, machine learning annotation agencies, BPO operations, and active communities**. It seamlessly bridges **Discord Voice Engagement Tracking** with **ECODA Platform Workforce Productivity Management** through an interactive UI, self-updating live leaderboards, bi-monthly cutoff cycles, and robust role-based governance.

---

## 📑 Table of Contents

- [🌟 System Architecture Overview](#-system-architecture-overview)
- [✨ Core Capabilities](#-core-capabilities)
  - [1. 💼 ECODA Workforce Management](#1--ecoda-workforce-management)
  - [2. 🎙️ Real-Time Discord Voice Tracking & Moderation](#2-️-real-time-discord-voice-tracking--moderation)
  - [3. 📊 Dedicated Live Dual-Dashboard Channel](#3--dedicated-live-dual-dashboard-channel)
  - [4. 📅 Bi-Monthly Cutoff Cycle Engine](#4--bi-monthly-cutoff-cycle-engine)
- [📋 In-Depth Slash Command Reference](#-in-depth-slash-command-reference)
  - [💼 ECODA Workforce Commands](#-ecoda-workforce-commands)
  - [📊 Live Dashboard & Cutoff History Commands](#-live-dashboard--cutoff-history-commands)
  - [🎙️ Discord Voice Activity Commands](#-discord-voice-activity-commands)
- [📅 Interactive Calendar Date Picker](#-interactive-calendar-date-picker)
- [🛡️ Access Control & Role Governance](#-access-control--role-governance)
- [📑 Supported File Formats (`.csv` / `.xlsx`)](#-supported-file-formats-csv--xlsx)
- [🗄️ Database Architecture & Migration Safety](#-database-architecture--migration-safety)
- [⚙️ Environment Variables Configuration (`.env`)](#-environment-variables-configuration-env)
- [🚀 Deployment & 24/7 Hosting Guide](#-deployment--247-hosting-guide)
  - [Option A: 24/7 Ubuntu/Debian VPS (Recommended)](#option-a-247-ubuntudebian-vps-recommended)
  - [Option B: Local Machine (Windows / macOS / Linux)](#option-b-local-machine-windows--macos--linux)
- [🔄 Updating the Bot on VPS](#-updating-the-bot-on-vps)
- [❓ Frequently Asked Questions (FAQ)](#-frequently-asked-questions-faq)

---

## 🌟 System Architecture Overview

In distributed organizations (such as data annotation agencies and BPO firms), supervisors require two distinct metrics:
1. **Real-time Voice Presence**: Monitoring whether staff are actively collaborating in voice rooms, sitting muted, or lingering idle while deafened.
2. **Platform Work Hours (ECODA)**: Processing verified daily work spreadsheets uploaded by Team Leaders, tracking bi-monthly cutoff productivity, separating Checker and Labeler tiers, and auditing inactive staff (0 hours).

```
                            ┌──────────────────────────────────────────────┐
                            │            Discord Gateway & Events          │
                            └──────────────┬───────────────────────────────┘
                                           │ on_voice_state_update
                                           ▼
                            ┌──────────────────────────────────────────────┐
                            │       In-Memory Buffering (utils.py)         │
                            │ - active_sessions: {user_id: session_data}   │
                            │ - deafened & AFK move timestamps             │
                            └──────────────┬───────────────┬───────────────┘
                                           │               │
                          Periodic Sync    │               │ AFK Loop (30s)
                          (Every 60s)      ▼               ▼
                            ┌──────────────────────────────┐
                            │   SQLite DB (voice_stats.db) │
                            │ ──────────────────────────── │
                            │ • voice_activity (3 states)  │
                            │ • ecoda_records (work hours) │
                            │ • bot_settings (configs)     │
                            │ • ecoda_blacklist (excluded) │
                            └──────────────┬───────────────┘
                                           │
                ┌──────────────────────────┴──────────────────────────┐
                ▼                                                     ▼
     ┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
     │       Interactive Slash Commands    │   │    Dedicated Live Channel Embeds    │
     │ • /stats, /leaderboard              │   │ • 🏆 Live Voice Leaderboard         │
     │ • /rolestats, /report               │   │ • 💼 Live ECODA Leaderboard         │
     │ • /ecoda_upload, /ecoda_add         │   │ (Persistent interactive UI buttons, │
     │ • /ecoda_edit, /ecoda_delete        │   │  paginated, auto-refreshed every    │
     │ • /ecoda_delete_date, /ecoda_reset  │   │  5 minutes and upon sheet upload)   │
     │ • /ecoda_exclude, /cutoff_history   │   │                                     │
     └─────────────────────────────────────┘   └─────────────────────────────────────┘
```

---

## ✨ Core Capabilities

### 1. 💼 ECODA Workforce Management
* **Spreadsheet Ingestion (`/ecoda_upload`)**: Upload `.xlsx` or `.csv` sheets with automatic column detection, username resolution, role mapping, and team assignment.
* **Separated Ranking Tiers**:
  * **🏷️ Labelers Ranking**: Ranks labelers (`default_role = 0`) starting from #1 with top badges (`🥇`, `🥈`, `🥉`).
  * **🔍 Checkers Ranking**: Ranks QA/Checkers (`default_role = 1`) in an independent leaderboard.
* **Active vs. Inactive Workforce Audits**:
  * **`🟢 Active Members`**: Workers with `work_time > 0h` ranked by logged hours.
  * **`🔴 Inactive (0h)`**: Instantly lists all workers who logged `0 hours` for the selected period alongside their team name so supervisors can audit attendance immediately.
* **Manual Hour Logging & Adjustments (`/ecoda_add`, `/ecoda_edit`)**:
  * Add missed records or adjust existing hours for any worker with custom dates or interactive calendar selection.
* **Multi-Worker Deletion & Date Wiping (`/ecoda_delete`, `/ecoda_delete_date`)**:
  * Remove records for multiple workers simultaneously using comma-separated lists (`e.g. Worker1, Worker2, @User`).
  * Delete records across all dates, today/yesterday, or a specific calendar date.
  * Wipe all uploaded records for a whole date if an incorrect file was uploaded.
* **Safe ECODA Reset (`/ecoda_reset`)**:
  * Wipes all ECODA work records (`ecoda_records`) with a 2-step confirmation prompt.
  * **Guaranteed Voice Safety**: Discord Voice Activity data is stored in a separate table (`voice_activity`) and remains **100% untouched**.
* **External Worker Blacklist (`/ecoda_exclude`)**:
  * Exclude external or freelance workers from appearing on the leaderboards. Supports adding multiple workers at once.

### 2. 🎙️ Real-Time Discord Voice Tracking & Moderation
* **Granular Three-State Tracking**:
  * **🟢 Unmuted**: Actively speaking/listening.
  * **🟡 Muted**: Microphone muted, but listening.
  * **🔴 Deafened**: Audio deafened (highest priority state).
* **Automated AFK & Deafen Moderation**:
  * Members deafened for $\ge 5$ minutes are automatically moved to the designated AFK voice channel.
  * Members remaining in the AFK channel for $\ge 5$ minutes are disconnected from voice to free server resources.
* **Graphical Charts (`/stats`)**: Dynamically renders an audio distribution donut chart and top 5 channels bar chart via `matplotlib`.
* **Role Auditing (`/rolestats`)**: Audits collective voice time for any role, provides active/inactive filters, and attaches an itemized CSV spreadsheet.
* **Automated Monthly Archive**: Generates and posts a server-wide voice activity CSV to the private admin channel at `00:00` on the 1st of every month.

### 3. 📊 Dedicated Live Dual-Dashboard Channel
* Deploys two permanent, self-updating live embeds into a dedicated read-only channel via `/setup_live_leaderboard`:
  1. **🏆 Live Discord Voice Activity Leaderboard**
  2. **💼 Live ECODA Activity Leaderboard**
* **Interactive Persistent Buttons**:
  * **Cutoff Switchers**: `[ ⏳ Current Cutoff ]` and `[ ⏪ Previous Cutoff ]`.
  * **Role Switchers (ECODA)**: `[ 🏷️ Labelers ]`, `[ 🔍 Checkers ]`, `[ 👥 All Roles ]`.
  * **Status Switchers (ECODA)**: `[ 🟢 Active Members ]` and `[ 🔴 Inactive (0h) ]`.
  * **Pagination Controls**: `[ ◀️ Prev ]`, `[ 📄 Page X/Y ]`, `[ Next ▶️ ]`.
  * **Instant Refresh**: `[ 🔄 Refresh ]`.

### 4. 📅 Bi-Monthly Cutoff Cycle Engine
* Productivity is calculated across two official monthly cutoffs:
  * **1st Cutoff**: Days `1` to `15` of the month.
  * **2nd Cutoff**: Days `16` to the `Last Day` of the month.
* When a cutoff ends, the live leaderboards automatically transition to the new cutoff period.
* Use `/cutoff_history` to inspect any historical cutoff for either Voice or ECODA records.

---

## 📋 In-Depth Slash Command Reference

### 💼 ECODA Workforce Commands

---

#### 1. `/ecoda_upload`
* **Description:** Uploads a daily ECODA work hours sheet (`.csv` or `.xlsx`). The bot parses worker rows, matches Discord accounts, saves hours, and automatically refreshes the live leaderboards.
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `file` *(Required, Attachment)*: The spreadsheet file (`.xlsx` or `.csv`).
  * `team` *(Optional, String)*: Team name for this upload (e.g. `Alpha Team`, `Titans`).
  * `date` *(Optional, String)*: Record date in `YYYY-MM-DD` format (defaults to today in local timezone).
* **Channel Restriction:** If an upload channel is configured via `/ecoda_set_channel`, this command can only be used in that channel.

---

#### 2. `/ecoda_add`
* **Description:** Manually logs or adds missed work hours for a worker.
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `worker` *(Required, String)*: Worker's Discord mention (`@user`) or exact sheet name (e.g. `ARC_Shikto`).
  * `hours` *(Required, Number)*: Hours worked (e.g. `3.5`, `1.25`).
  * `role` *(Optional, Choice)*: `🏷️ Labeler` (`0`, Default) or `🔍 Checker` (`1`).
  * `team` *(Optional, String)*: Optional team name.
  * `date` *(Optional, String)*: Date in `YYYY-MM-DD`. If left empty, an **interactive Calendar Date Picker** appears for one-click selection.

---

#### 3. `/ecoda_edit`
* **Description:** Corrects work hours or team name for an existing worker record on a specific date.
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `worker` *(Required, String)*: Worker's Discord mention (`@user`) or sheet name.
  * `hours` *(Required, Number)*: Corrected hours (e.g. `2.5` or `0`).
  * `team` *(Optional, String)*: Updated team name.
  * `date` *(Optional, String)*: Date in `YYYY-MM-DD`. If left empty, launches the **Calendar Date Picker**.
  * `note` *(Optional, String)*: Optional reason or audit note for the modification.

---

#### 4. `/ecoda_delete`
* **Description:** Deletes records for one or multiple workers from the ECODA database.
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `workers` *(Required, String)*: Comma-separated worker sheet names or mentions (e.g. `Rahul, Suman, @Alex`).
  * `date` *(Optional, String)*: 
    * Specific date (`YYYY-MM-DD`),
    * `'all'` (deletes all records across all time for these workers), or
    * Leave empty to open an interactive dialog with buttons: `[ 🗑️ Delete ALL Dates ]`, `[ ☀️ Today ]`, `[ ⏪ Yesterday ]`, and `[ 📅 Pick from Calendar ]`.

---

#### 5. `/ecoda_delete_date`
* **Description:** Wipes all uploaded worker records for an entire specific date (e.g. if an invalid or duplicate sheet was uploaded for a day).
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `date` *(Optional, String)*: Target date (`YYYY-MM-DD`). If omitted, opens the interactive Calendar Date Picker.

---

#### 6. `/ecoda_reset`
* **Description:** Completely wipes ALL records from the ECODA database (`ecoda_records`) to allow a fresh start for a new cycle or system reset.
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:** *None.*
* **Safety Mechanism:**
  * Displays an interactive confirmation prompt:
    * `[ ⚠️ Yes, Reset All ECODA Data ]` *(Danger Button)*
    * `[ ❌ Cancel ]` *(Secondary Button)*
  * **100% Voice Data Preservation**: Does not touch `voice_activity` or bot configurations. Only ECODA records are removed.

---

#### 7. `/ecoda_exclude`
* **Description:** Manages the external worker blacklist to permanently hide external/freelance labelers from the leaderboard. Excluded workers are also ignored during future spreadsheet uploads.
* **Permissions:** Team Leader / Checker Role or Server Administrator.
* **Parameters:**
  * `action` *(Required, Choice)*:
    * `➕ Add to Blacklist`: Excludes workers.
    * `➖ Remove from Blacklist`: Unhides workers.
    * `📋 List All Excluded Workers`: Displays all currently blacklisted names.
  * `workers` *(Optional, String)*: Comma-separated names or mentions (e.g. `John, Mark, David`).
  * `delete_records` *(Optional, Boolean)*: If `True`, also removes their historical records from the database.

---

#### 8. `/ecoda_leaderboard`
* **Description:** Displays an interactive standalone ECODA leaderboard embed with pagination and filters.
* **Permissions:** Everyone.
* **Parameters:**
  * `timeframe` *(Optional, Choice)*: `⏳ Current Cutoff`, `⏪ Previous Cutoff`, `☀️ Today`, `📅 This Week`, `🟢 This Month`, `🔵 All Time`.
  * `role_filter` *(Optional, Choice)*: `🏷️ Labelers Only`, `🔍 Checkers Only`, `👥 All Roles`.
  * `status` *(Optional, Choice)*: `🟢 Active Members (>0h)` or `🔴 Inactive Members (0h)`.

---

#### 9. `/ecoda_set_role`
* **Description:** Configures the Discord role authorized to upload sheets and manage ECODA records.
* **Permissions:** Server Administrator only.
* **Parameters:**
  * `role` *(Required, Role)*: Target role (e.g. `@Team Leader` or `@Checker`).

---

#### 10. `/ecoda_set_channel`
* **Description:** Restricts `/ecoda_upload` commands to a specific text channel to prevent clutter in general channels.
* **Permissions:** Server Administrator only.
* **Parameters:**
  * `channel` *(Required, Text Channel)*: Target upload channel (e.g. `#ecoda-uploads`).

---

#### 11. `/ecoda_settings`
* **Description:** Displays an embed summarizing current ECODA configuration settings (assigned leader role, upload channel, and live leaderboard channel).
* **Permissions:** Everyone / Admin.
* **Parameters:** *None.*

---

### 📊 Live Dashboard & Cutoff History Commands

---

#### 12. `/setup_live_leaderboard`
* **Description:** Deploys two permanent, self-updating live leaderboard embeds into a designated channel:
  1. **🏆 Live Voice Activity Leaderboard**
  2. **💼 Live ECODA Activity Leaderboard**
  Both embeds feature persistent interactive buttons (cutoffs, role toggles, active/inactive filters, pagination, and refresh) that survive bot restarts.
* **Permissions:** Server Administrator only.
* **Parameters:**
  * `channel` *(Required, Text Channel)*: Target channel (e.g. `#leaderboard`).

---

#### 13. `/cutoff_history`
* **Description:** Inspects any past or present cutoff leaderboard for either Voice Activity or ECODA Work Hours with pagination support.
* **Permissions:** Everyone.
* **Parameters:**
  * `category` *(Required, Choice)*: `🔊 Voice Activity Leaderboard` or `💼 ECODA Work Hours Leaderboard`.
  * `part` *(Required, Choice)*: `1st Cutoff (1st - 15th)` or `2nd Cutoff (16th - End of Month)`.
  * `month` *(Optional, Integer)*: Month number (`1` to `12`, defaults to current month).
  * `year` *(Optional, Integer)*: Four-digit year (e.g. `2026`, defaults to current year).

---

### 🎙️ Discord Voice Activity Commands

---

#### 14. `/stats`
* **Description:** Generates an interactive visual voice statistics dashboard for yourself or another user. Renders an audio state donut chart and top 5 channels bar chart via `matplotlib`.
* **Permissions:** Everyone (Restricted to `STATS_CHANNEL_ID` if configured).
* **Parameters:**
  * `user` *(Optional, Member)*: Target user (defaults to command runner).
  * `start_date` *(Optional, String)*: Custom start date (`YYYY-MM-DD`).
  * `end_date` *(Optional, String)*: Custom end date (`YYYY-MM-DD`).

---

#### 15. `/leaderboard`
* **Description:** Displays the server-wide Discord voice activity leaderboard with dropdown filters for Current Cutoff, Previous Cutoff, Today, This Week, This Month, and All Time.
* **Permissions:** Everyone (Restricted to `STATS_CHANNEL_ID` if configured).
* **Parameters:**
  * `start_date` *(Optional, String)*: Custom start date (`YYYY-MM-DD`).
  * `end_date` *(Optional, String)*: Custom end date (`YYYY-MM-DD`).

---

#### 16. `/rolestats`
* **Description:** Audits the collective and individual voice time of all members possessing a specific server role. Features interactive active/inactive member filters and automatically generates an itemized CSV spreadsheet attachment.
* **Permissions:** Server Administrator or roles specified in `ROLESTATS_ALLOWED_ROLES`.
* **Parameters:**
  * `role` *(Required, Role)*: Target role (e.g. `@Annotators`).
  * `start_date` *(Optional, String)*: Start date (`YYYY-MM-DD`).
  * `end_date` *(Optional, String)*: End date (`YYYY-MM-DD`).

---

#### 17. `/report`
* **Description:** Manually exports and posts a comprehensive CSV spreadsheet containing every member's voice activity breakdown for the current month.
* **Permissions:** Everyone (Restricted to `STATS_CHANNEL_ID` if configured).
* **Parameters:** *None.*

---

## 📅 Interactive Calendar Date Picker

Whenever commands require a date (e.g. `/ecoda_add`, `/ecoda_edit`, `/ecoda_delete`, `/ecoda_delete_date`), leaving the date parameter blank triggers an **interactive Calendar Date Picker View**:

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

* **One-Click Shortcuts**: Select today or yesterday with a single tap.
* **Cutoff Dropdown**: Quickly choose dates within the active bi-monthly cycle.
* **Full Month Navigation**: Browse through days and months using prev/next buttons.

---

## 🛡️ Access Control & Role Governance

| Action / Command Group | Default Permissions | How to Customize |
| :--- | :--- | :--- |
| **Upload / Manage ECODA** (`/ecoda_*`) | Administrator or users with role matching `'checker'` | Set with `/ecoda_set_role role:@YourRole` |
| **ECODA Upload Channel** | Any text channel | Lock to one channel with `/ecoda_set_channel channel:#uploads` |
| **Setup Live Leaderboards** | Server Administrator (`administrator=True`) | Built-in Discord permission check |
| **Role Audits** (`/rolestats`) | Administrator | Set `ROLESTATS_ALLOWED_ROLES` in `.env` |
| **Voice Stats & Leaderboards** | Everyone | Restrict to one channel via `STATS_CHANNEL_ID` in `.env` |
| **Monthly Automated Report** | Delivered to private admin channel | Set `REPORT_CHANNEL_ID` in `.env` |

---

## 📑 Supported File Formats (`.csv` / `.xlsx`)

The `/ecoda_upload` command accepts `.csv` and Excel `.xlsx` spreadsheets.

### Expected Columns (Case-Insensitive):
The parser automatically matches column headers using standard names and aliases:

| Standard Column | Accepted Aliases | Description |
| :--- | :--- | :--- |
| `user_name` | `username`, `worker_name`, `name`, `ecoda_name` | Worker's sheet name (e.g. `ARC_Shikto Kumar Das`) |
| `default_role` | `role`, `role_type` | `0` for **Labeler**, `1` for **Checker** |
| `work_time` | `work_hour`, `hours`, `time` | Work hours in decimal format (e.g. `3.5`, `1.578`, `0`) |
| `group_id` | `group` | *(Optional)* Department / Project ID |
| `team_id` | `team` (numeric) | *(Optional)* Team numerical ID |
| `team_name` | `team` (text), `team_title` | *(Optional)* Team name string (e.g. `Alpha Team`) |

### Example CSV:
```csv
user_name,default_role,work_time,group_id,team_id
ARC_Nasar Ahmed Hridoy,0,0,901,202
ARC_Shikto Kumar Das,0,1.578,901,202
ARC_Sadman Sakib,1,3.250,901,202
ARC_Adil Arham,0,0,901,202
```

---

## 🗄️ Database Architecture & Migration Safety

The bot runs on **SQLite** using `aiosqlite`, providing ACID transactions with zero external server dependencies.

```sql
-- Discord Voice Channel Tracking (Daily aggregate per user & channel)
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

-- ECODA Platform Work Hours
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

-- Dynamic Key-Value Store for In-Server Bot Configuration
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- External Workers Blacklist
CREATE TABLE IF NOT EXISTS ecoda_blacklist (
    ecoda_name TEXT PRIMARY KEY,
    added_by INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Self-Healing Auto-Migrations:
Upon startup (`init_db()`), the bot queries table schemas. If columns (such as `team_name`) are missing in older databases, it dynamically executes non-destructive `ALTER TABLE` statements without data loss.

---

## ⚙️ Environment Variables Configuration (`.env`)

Create a `.env` file in the project root:

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

## 🚀 Deployment & 24/7 Hosting Guide

### Option A: 24/7 Ubuntu/Debian VPS (Recommended)

#### 1. Install System Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y
```

#### 2. Clone the Repository
```bash
cd ~
git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
cd Discord-Time-Counter-Bot
```

#### 3. Create & Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Configure `.env`
```bash
cp .env.example .env
nano .env
```
*(Paste your bot token and configurations. Save with `Ctrl+O`, `Enter`, then exit with `Ctrl+X`)*

#### 5. Configure Systemd Daemon Service
Create a service file:
```bash
sudo nano /etc/systemd/system/counterbot.service
```

Paste the following (replace `ubuntu` with your Linux username):
```ini
[Unit]
Description=Discord Time Counter & ECODA Bot
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

#### 6. Start the Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable counterbot.service
sudo systemctl start counterbot.service
```

#### 7. Verify Status & Logs
```bash
# Check service status
sudo systemctl status counterbot.service

# View live output logs
sudo journalctl -u counterbot.service -f
```

---

### Option B: Local Machine (Windows / macOS / Linux)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
   cd Discord-Time-Counter-Bot
   ```
2. **Create virtual environment**:
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
   copy .env.example .env   # On Windows
   cp .env.example .env     # On macOS/Linux
   ```
5. **Run the bot**:
   ```bash
   python bot.py
   ```

---

## 🔄 Updating the Bot on VPS

Whenever new features or bug fixes are pushed to GitHub:

```bash
cd ~/Discord-Time-Counter-Bot

# 1. Pull the latest commits
git pull origin main

# 2. Restart the bot service
sudo systemctl restart counterbot.service

# 3. Check logs to confirm clean startup
sudo journalctl -u counterbot.service -n 20 --no-pager
```

---

## ❓ Frequently Asked Questions (FAQ)

#### Q1: Does running `/ecoda_reset` delete voice activity tracking?
**A:** **No.** Discord voice tracking data is stored in the `voice_activity` table, while ECODA records are stored in `ecoda_records`. Running `/ecoda_reset` only wipes `ecoda_records`. Your voice statistics and channel history remain 100% intact.

#### Q2: What happens if a worker changes their Discord nickname?
**A:** The bot dynamically resolves names on every sync. If a worker updates their Discord server nickname to match their sheet name, the bot will immediately associate their Discord mention (`<@user_id>`) across all dashboards.

#### Q3: How do we set up the dedicated `#leaderboard` channel?
**A:** Run `/setup_live_leaderboard channel:#leaderboard`. In the channel settings, give `@everyone` permissions to **View Channel** and **Read Message History**, but **deny** **Send Messages** and **Add Reactions**. The bot will post and continuously maintain the self-updating live embeds.

#### Q4: How do we inspect 0-hour inactive workers for daily attendance?
**A:** On the Live ECODA Leaderboard embed, click the **`[ 🔴 Inactive (0h) ]`** button. The embed will instantly show all workers recorded with 0 hours for that cutoff period alongside their team name.

---

## 📜 License

Distributed under the **MIT License**. You are free to modify, extend, and deploy this project for personal and commercial operations.