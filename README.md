# 🎙️ Discord Time Counter & ECODA Workforce Bot — v3.0

An enterprise-ready, asynchronous Discord bot built with **`discord.py`**, **`aiosqlite`**, and **`matplotlib`**. It provides unified **Discord Voice Activity Tracking** and **ECODA Workforce Productivity Management**, featuring bi-monthly cutoff cycles, separate ranking tiers for Labelers and Checkers, active vs. inactive worker auditing, dynamic live leaderboard channels, and automated CSV/graphical exports.

---

## 🌟 Executive Overview

In remote workflows and data annotation environments (e.g., machine learning labeling agencies, BPO teams, distributed offices), team managers need two critical metrics:
1. **Real-time Voice Engagement**: Knowing who is actively communicating in Discord voice rooms versus sitting muted or deafened.
2. **Platform Work Hours (ECODA)**: Aggregating verified daily work sheets uploaded by Team Leaders, tracking bi-monthly cutoff productivity, separating Checker and Labeler performance, and identifying inactive members who logged zero hours.

**Discord Time Counter Bot v3.0** combines both systems into a single modular bot with zero external database dependencies (built on high-performance SQLite), dynamic slash commands, and persistent interactive UI message views.

---

## 🚀 Key Features

### 1. 💼 ECODA Workforce Activity & Sheet Ingestion
* **Daily Sheet Upload (`/ecoda_upload`)**: Team Leaders upload `.csv` or `.xlsx` work hour logs. The bot parses worker names, roles (Labeler vs. Checker), work hours, group IDs, and team IDs.
* **Team Name Association (`team` option)**: Team leaders can assign their team name (e.g., `Alpha Team`, `Titans`) during upload. The team name is persisted in the database and shown on all dashboards.
* **Intelligent Member Resolution**: Automatically matches sheet usernames with Discord nicknames, display names, or global usernames to link Discord mentions `<@user_id>`. Unmatched workers are displayed with their sheet name and dynamically re-link if they update their Discord nicknames.
* **Separated Ranking Tiers**:
  * **🏷️ Labelers Ranking**: Ranks only Labelers (`role_type = 0`) starting from #1 (`🥇`, `🥈`, `🥉`).
  * **🔍 Checkers Ranking**: Ranks only Checkers (`role_type = 1`) in their own independent hierarchy.
* **Active vs. Inactive Workforce Auditing**:
  * **`🟢 Active Members`**: Workers with `work_time > 0h` ranked by total hours.
  * **`🔴 Inactive (0h)`**: Instantly lists all workers recorded with `0 hours` for the selected period alongside their team name so supervisors can identify inactive staff immediately.
* **Correction System (`/ecoda_edit`)**: If a team leader accidentally uploads duplicate, faulty, or wrong data, supervisors can correct a worker's hours or team name for any date without wiping the database.

### 2. 📅 Bi-Monthly Cutoff Tracking (1st & 2nd Cutoffs)
* In workforce management, productivity is calculated across two monthly cutoff periods:
  * **1st Cutoff**: `1st` to `15th` of the month.
  * **2nd Cutoff**: `16th` to the `Last Day` of the month.
* **Automatic Reset**: When a new cutoff begins, the live leaderboards automatically transition to the new cutoff period.
* **Cutoff History Explorer (`/cutoff_history`)**: Supervisors can inspect any past or present cutoff for both Voice and ECODA data by specifying year, month, and cutoff part (1 or 2).

### 3. 📊 Dedicated Live Dynamic Leaderboards Channel (`/setup_live_leaderboard`)
* Deploys two permanent, self-updating live leaderboard embeds into a dedicated read-only channel:
  1. **🏆 Live Discord Voice Activity Leaderboard**
  2. **💼 Live ECODA Activity Leaderboard**
* **Persistent Button Controls** (Survives bot restarts):
  * **Cutoff Switchers**: `[ ⏳ Current Cutoff ]` and `[ ⏪ Previous Cutoff ]`.
  * **Role Switchers (ECODA)**: `[ 🏷️ Labelers ]`, `[ 🔍 Checkers ]`, `[ 👥 All Roles ]`.
  * **Status Switchers (ECODA)**: `[ 🟢 Active Members ]` and `[ 🔴 Inactive (0h) ]`.
  * **Pagination**: `[ ◀️ Prev ]`, `[ 📄 Page X/Y ]`, `[ Next ▶️ ]`.
  * **Manual Sync**: `[ 🔄 Refresh ]`.
* **Background Loop**: Auto-refreshes both boards every 5 minutes and updates immediately whenever an ECODA file is uploaded or edited.

### 4. 🎙️ Real-Time Discord Voice Tracking & Audio State Moderation
* **Granular Audio States**:
  * **🟢 Unmuted**: Actively speaking and listening.
  * **🟡 Muted**: Microphone muted, but listening.
  * **🔴 Deafened**: Server or self-deafened (highest priority).
* **Automated AFK & Deafen Moderation**:
  * Members remaining deafened for $\ge 5$ minutes are automatically moved to the designated AFK channel.
  * Members staying in the AFK channel for $\ge 5$ minutes are automatically disconnected to free voice server resources.
* **Interactive Graphical Dashboards (`/stats`)**: Generates an embed with an audio state distribution donut chart and top 5 channels bar chart rendered dynamically via `matplotlib`.
* **Role Activity Auditing (`/rolestats`)**: Audits collective and individual voice activity for any server role (e.g. `@Annotators`, `@Support`) with interactive active/inactive filters and automated CSV spreadsheet generation.
* **Scheduled Monthly Archive**: Automatically generates a complete server-wide voice activity CSV report at `00:00` on the 1st of each month and delivers it to the designated admin channel.

### 5. 🛡️ Role & Channel Governance
* **Upload Channel Lock (`/ecoda_set_channel`)**: Restricts ECODA uploads to a designated channel so operational chat channels stay clean.
* **Leader Role Permission (`/ecoda_set_role`)**: Restricts ECODA uploads and edits to verified Team Leaders, Checkers, and Server Administrators.
* **Safe Database Migrations**: Self-healing SQLite schema that automatically inspects and updates tables (`ALTER TABLE ... ADD COLUMN`) without data loss.

---

## 🏗️ Architecture & Project Structure

The codebase is organized following modern `discord.py` **Cogs** architecture for maintainability and modularity:

```
Discord-Time-Counter-Bot/
├── bot.py                  # Bot entry point, intents, setup_hook & cog loader
├── utils.py                # Database migrations, DB queries, UI views & helpers
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variables template
├── .env                    # Secret environment credentials (untracked)
├── voice_stats.db          # SQLite persistent database (created automatically)
└── cogs/                   # Modular feature extensions
    ├── __init__.py         # Package initializer
    ├── voice_tracking.py   # Gateway listener, AFK enforcer & periodic sync
    ├── stats.py            # /stats command & visual matplotlib charts
    ├── leaderboard.py      # /leaderboard, /cutoff_history & /setup_live_leaderboard
    ├── ecoda.py            # /ecoda_upload, /ecoda_edit, /ecoda_leaderboard & admin configs
    ├── report.py           # /report command (manual monthly CSV export)
    └── rolestats.py        # /rolestats command & role audit engine
```

### Data Pipeline Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │            Discord Gateway & Events          │
                       └──────────────┬───────────────────────────────┘
                                      │ on_voice_state_update
                                      ▼
                       ┌──────────────────────────────────────────────┐
                       │       In-Memory Buffering (utils.py)         │
                       │ - active_sessions: {user_id: session_data}   │
                       │ - deafen_timestamps & afk_moved_timestamps   │
                       └──────────────┬───────────────┬───────────────┘
                                      │               │
                     Periodic Sync    │               │ AFK Loop (30s)
                     (Every 60s)      ▼               ▼
                       ┌──────────────────────────────┐
                       │   SQLite DB (voice_stats.db) │
                       │ ──────────────────────────── │
                       │ • voice_activity             │
                       │ • ecoda_records (team_name)  │
                       │ • bot_settings               │
                       └──────────────┬───────────────┘
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           ▼                                                     ▼
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│       Interactive Slash Commands    │   │     Live Dedicated Channel Embeds   │
│ • /stats, /leaderboard              │   │ • 🏆 Live Voice Leaderboard         │
│ • /rolestats, /report               │   │ • 💼 Live ECODA Leaderboard         │
│ • /ecoda_upload, /ecoda_edit        │   │ (Paginated, Cutoffs, Role & Status) │
│ • /cutoff_history                   │   │ (Auto-refreshed every 5 minutes)    │
└─────────────────────────────────────┘   └─────────────────────────────────────┘
```

---

## 🎯 Primary Use Cases

1. **AI / Machine Learning Data Labeling Agencies**:
   * Team leaders upload daily CSV/Excel sheets exported from internal portals.
   * Work hours are automatically linked to Discord worker accounts.
   * Checkers and Labelers are ranked separately to drive healthy competition.
   * Inactive workers (0 hours) are quickly identified for daily attendance checks.
2. **Bi-Monthly Payroll & Invoicing Verifications**:
   * Managers check `/cutoff_history` at the end of the 1st Cutoff (1st-15th) or 2nd Cutoff (16th-End) to verify hours worked before processing compensation.
3. **Remote Teams & BPO Operations**:
   * Audits active working hours across voice rooms.
   * Prevents employees from idling while deafened via automated AFK kicks.
4. **Gaming & Study Communities**:
   * Gamifies voice room activity with real-time dynamic leaderboards and medals (`🥇`, `🥈`, `🥉`).

---

## 📋 Comprehensive Slash Command Reference

### 1. 💼 ECODA Workforce Management Commands

| Command | Arguments | Permissions | Description |
| :--- | :--- | :--- | :--- |
| **`/ecoda_upload`** | `file` *(Required)*<br>`team` *(Optional)*<br>`date` *(Optional)* | Team Leader / Checker / Admin | Uploads a `.csv` or `.xlsx` work hours sheet. Links names to Discord accounts, assigns team name, and refreshes live leaderboards. Restricted to upload channel if configured. |
| **`/ecoda_edit`** | `worker` *(Required)*<br>`hours` *(Required)*<br>`team` *(Optional)*<br>`date` *(Optional)*<br>`note` *(Optional)* | Team Leader / Checker / Admin | Corrects or adjusts a worker's hours or team name for a specific date. Useful when duplicate or faulty sheets were uploaded. |
| **`/ecoda_leaderboard`** | `timeframe` *(Optional)*<br>`role_filter` *(Optional)*<br>`status` *(Optional)* | Everyone | Interactive multi-page ECODA leaderboard. Filter by Cutoff, Labelers/Checkers, or Active/Inactive (0h) members. |
| **`/ecoda_set_role`** | `role` *(Required)* | Administrator | Sets the server role authorized to run `/ecoda_upload` and `/ecoda_edit`. |
| **`/ecoda_set_channel`**| `channel` *(Required)* | Administrator | Sets the designated text channel where team leaders must upload ECODA files. |
| **`/ecoda_settings`** | *None* | Team Leader / Admin | Displays the current ECODA upload channel, authorized role, and live boards channel. |

### 2. 🏆 Live Boards & Cutoff History Commands

| Command | Arguments | Permissions | Description |
| :--- | :--- | :--- | :--- |
| **`/setup_live_leaderboard`** | `channel` *(Required)* | Administrator | Deploys persistent, interactive live Voice and ECODA leaderboards into the selected channel. |
| **`/cutoff_history`** | `category` *(Required)*<br>`part` *(Required)*<br>`month` *(Optional)*<br>`year` *(Optional)* | Everyone | Browse historical Cutoff leaderboards (1st Cutoff: 1-15, 2nd Cutoff: 16-End) for Voice or ECODA with pagination. |

### 3. 🎙️ Discord Voice Activity Commands

| Command | Arguments | Permissions | Description |
| :--- | :--- | :--- | :--- |
| **`/stats`** | `user` *(Optional)*<br>`start_date` *(Optional)*<br>`end_date` *(Optional)* | Everyone *(Channel lockable)* | Displays an interactive personal voice statistics dashboard with donut charts and channel breakdown. |
| **`/leaderboard`** | `start_date` *(Optional)*<br>`end_date` *(Optional)* | Everyone *(Channel lockable)* | Interactive server voice leaderboard with dropdown timeframe filter. |
| **`/rolestats`** | `role` *(Required)*<br>`start_date` *(Optional)*<br>`end_date` *(Optional)* | Admin or `ROLESTATS_ALLOWED_ROLES` | Audits collective voice time for any role with active/inactive member filters and attaches an itemized CSV spreadsheet. |
| **`/report`** | *None* | Everyone *(Channel lockable)* | Exports and sends a full CSV breakdown of voice activity for the current month. |

---

## 📑 File Format Guide for `/ecoda_upload`

The bot accepts standard `.csv` and Excel `.xlsx` spreadsheets. 

### Expected Columns (Header Row):
The parser is case-insensitive and automatically detects standard headers:

| Standard Header | Supported Aliases | Purpose |
| :--- | :--- | :--- |
| `user_name` | `username`, `worker_name`, `name`, `ecoda_name` | Worker's full name or sheet nickname (e.g. `ARC_Shikto Kumar Das`) |
| `default_role` | `role`, `role_type` | `0` for **Labeler**, `1` for **Checker** |
| `work_time` | `work_hour`, `hours`, `time` | Decimal hours worked (e.g. `2.5`, `1.578`, `0`) |
| `group_id` | `group` | *(Optional)* Department / Project identifier (e.g. `901`) |
| `team_id` | `team` (numeric) | *(Optional)* Numeric team ID (e.g. `202`) |
| `team_name` | `team` (text), `team_title` | *(Optional)* Team name string (e.g. `Alpha Team`). If omitted, the `team` parameter in `/ecoda_upload` is applied. |

### Sample CSV Structure:
```csv
user_name,default_role,work_time,group_id,team_id
ARC_Nasar Ahmed Hridoy,0,0,901,202
ARC_Shikto Kumar Das,0,1.578,901,202
ARC_Sadman Sakib,1,3.250,901,202
ARC_Adil Arham,0,0,901,202
```

---

## ⚙️ Environment Variables Configuration (`.env`)

Create a `.env` file in the root directory (based on `.env.example`):

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

# Voice channel ID where users deafened > 5 mins are moved
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

## 🗄️ Database Architecture & Migration Safety

The bot runs on **SQLite** via `aiosqlite`, providing ACID-compliant transactions with zero external server dependencies.

```sql
-- Daily Voice Channel Activity
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

-- ECODA Work Hours Records
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

-- Dynamic Key-Value Store for In-Server Configuration
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

### Self-Healing Auto-Migrations
When the bot starts up (`init_db()`), it queries `PRAGMA table_info` for all tables. If a newer column (such as `team_name`) is absent in an existing database on your VPS, it executes:
```sql
ALTER TABLE ecoda_records ADD COLUMN team_name TEXT;
```
Existing historical voice and workforce data are **100% preserved**.

---

## 🛠️ Step-by-Step Setup & Installation Guide

### Option A: 24/7 Hosting on Ubuntu / Debian VPS (Recommended)

#### Step 1: Update Server Packages
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git curl -y
```

#### Step 2: Clone the Repository
```bash
cd ~
git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
cd Discord-Time-Counter-Bot
```

#### Step 3: Set Up Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Configure Credentials
```bash
cp .env.example .env
nano .env
```
*Fill in `BOT_TOKEN`, your timezone (e.g. `Asia/Dhaka`), and any optional channel IDs.*
*Press `Ctrl + O`, `Enter` to save, and `Ctrl + X` to exit.*

#### Step 5: Configure 24/7 Systemd Daemon Service
Create a systemd unit file:
```bash
sudo nano /etc/systemd/system/counterbot.service
```

Paste the following content (replace `your-username` with your actual Linux user, e.g. `ubuntu` or `root`):
```ini
[Unit]
Description=Discord Time Counter & ECODA Workforce Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/Discord-Time-Counter-Bot
ExecStart=/home/your-username/Discord-Time-Counter-Bot/.venv/bin/python /home/your-username/Discord-Time-Counter-Bot/bot.py
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

#### Step 7: Verify Service Status & Logs
```bash
# Check if active (running)
sudo systemctl status counterbot.service

# Stream live terminal output
sudo journalctl -u counterbot.service -f
```

---

### Option B: Local Setup (Windows / macOS / Linux)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
   cd Discord-Time-Counter-Bot
   ```
2. **Create and activate a virtual environment**:
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
4. **Create your `.env`**:
   ```bash
   copy .env.example .env
   ```
   *Edit `.env` with your bot token.*
5. **Run the bot**:
   ```bash
   python bot.py
   ```

---

## 🔒 Recommended Server Permissions for Live Leaderboards Channel

When you run `/setup_live_leaderboard channel:#leaderboard`:
1. Open Discord **Channel Settings** for that channel.
2. Go to **Permissions** ➔ **`@everyone`**:
   * **View Channel**: ✅ `Allow`
   * **Read Message History**: ✅ `Allow`
   * **Send Messages**: ❌ `Deny`
   * **Add Reactions**: ❌ `Deny`
3. Ensure the bot's role has:
   * **View Channel**: ✅ `Allow`
   * **Send Messages**: ✅ `Allow`
   * **Embed Links**: ✅ `Allow`
   * **Manage Messages** *(Optional, to pin the leaderboards)*: ✅ `Allow`

This keeps the leaderboard channel completely clean, prevents chat clutter, and allows everyone to click the interactive pagination, cutoff, role, and active/inactive filter buttons.

---

## 🔄 Updating the Bot on Your VPS

When updating files or pulling new changes from Git:

```bash
cd ~/Discord-Time-Counter-Bot

# If pulling from GitHub:
git pull

# Restart the background service:
sudo systemctl restart counterbot.service

# Check recent logs to ensure clean startup:
sudo journalctl -u counterbot.service -n 20
```

---

## ❓ Frequently Asked Questions (FAQ)

**Q: Do I lose past data when updating the bot?**  
**A:** No. All voice sessions and ECODA work hours are persisted in SQLite (`voice_stats.db`). The startup script automatically performs safe schema updates (`ALTER TABLE`) without touching existing records.

**Q: Why are some worker names showing as `**Name**` instead of `@User`?**  
**A:** If a worker's Discord nickname or username does not match the name in the uploaded sheet, the bot displays their sheet name in bold to ensure their hours are tracked. When the worker changes their Discord nickname to match their sheet name, the bot auto-links them on the next sync.

**Q: Can team leaders upload files in any channel?**  
**A:** By default, yes. However, an Administrator can lock uploads to a specific channel using `/ecoda_set_channel`. Once locked, uploads in any other channel will be rejected with an ephemeral notification directing the leader to the proper channel.

**Q: How do we inspect inactive members for the current cutoff?**  
**A:** On the Live ECODA Leaderboard in your dedicated channel, click the **`[ 🔴 Inactive (0h) ]`** button. The list will immediately refresh to display all workers logged with 0 hours, categorized by their team name.

---

## 📜 License

Distributed under the **MIT License**. You are free to use, modify, and distribute this software for personal and commercial purposes.