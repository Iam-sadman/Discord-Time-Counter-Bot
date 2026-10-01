# 🎙️ Discord Time Counter Bot — v2.0

An asynchronous, production-ready Discord bot built with **`discord.py`**, **`aiosqlite`**, and **`matplotlib`** that tracks user voice engagement, distinguishes audio states (Unmuted, Muted, Deafened), generates rich graphical dashboards, powers interactive paginated leaderboards, audits team/role activity with custom date ranges, and exports detailed CSV reports.

---

## 🚀 What's New in Version 2.0

* 👥 **Role Activity Auditing (`/rolestats`)**: Inspect collective and individual voice activity for any specific role (e.g., `@labelers`, `@Staff`) across custom date ranges.
* 🎛️ **Interactive Paginated UI**: Browse beyond the top 10 members using intuitive `◀ Prev` and `Next ▶` buttons.
* 🔘 **Dynamic State Filters**: Instantly toggle between **`🟢 Active`**, **`⚪ Inactive`** (0-hour members), and **`👥 All`** members.
* 📄 **Automated CSV Attachment**: Every role report automatically compiles a full member-by-member and channel-by-channel `.csv` spreadsheet attachment.
* 🔐 **Configurable Role Permissions**: Delegate `/rolestats` access to specific roles or managers via `ROLESTATS_ALLOWED_ROLES` in `.env` without granting full server Administrator rights.
* 📱 **Full-Width Embed Design**: Engineered with wide separators to ensure embeds expand to maximum width across Discord desktop and mobile apps.

---

## ⚙️ How It Works (Bot Mechanism)

```
                            ┌────────────────────────────────────┐
                            │    Discord Voice Gateway Events    │
                            └─────────────────┬──────────────────┘
                                              │ on_voice_state_update
                                              ▼
                            ┌────────────────────────────────────┐
                            │ In-Memory Sessions (active_sessions)│
                            │ - Real-time join timestamps        │
                            │ - State tracking & elapsed delta   │
                            └─────────┬────────────────┬─────────┘
                 Every 60s / Commands │                │ Every 30s Loop
                                      ▼                ▼
     ┌────────────────────────────────────────┐  ┌───────────────────────────────────┐
     │        SQLite (voice_stats.db)         │  │     AFK & Deafen Enforcer         │
     │ Daily record_date: YYYY-MM-DD          │  │ - Deafened > 5 min ➜ Move to AFK │
     │ ON CONFLICT DO UPDATE (Atomic counter) │  │ - In AFK > 5 min ➜ Disconnect    │
     └───────────────────┬────────────────────┘  └───────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         ▼                               ▼
┌──────────────────┐           ┌──────────────────┐
│ Interactive UI   │           │ Scheduled Export │
│ /stats           │           │ 1st of month     │
│ /leaderboard     │           │ Automated CSV to │
│ /rolestats       │           │ Admin Channel    │
└──────────────────┘           └──────────────────┘
```

1. **Granular Audio State Classification**:
   * **Deafened** (Highest priority): User has server deafen or self-deafen active.
   * **Muted**: User is muted (mic muted) but can hear.
   * **Unmuted**: User is actively transmitting and listening.

2. **In-Memory Buffering & Atomic Flushing**:
   * Real-time seconds are accumulated in-memory in `active_sessions`.
   * On channel switch, state toggle, or disconnect, the accumulated delta is committed to SQLite atomically.
   * A background task (`periodic_sync`) flushes all active sessions every 60 seconds to ensure no data is lost during unexpected shutdowns.

3. **Persistent Daily Aggregation**:
   * Stored in SQLite keyed by `(user_id, channel_id, record_date)`.
   * Using daily granularity (`YYYY-MM-DD`) allows querying any arbitrary date range (`start_date` to `end_date`), single days, weeks, months, or years with high performance.

4. **AFK & Deafen Auto-Moderation**:
   * Monitored every 30 seconds.
   * If a member stays deafened for $\ge 5$ minutes, the bot moves them to `AFK_CHANNEL_ID` (or disconnects them if no AFK channel is set).
   * If a member stays in the AFK channel for $\ge 5$ minutes, the bot disconnects them.

---

## 📋 Slash Commands

| Command | Permissions | Description |
| :--- | :--- | :--- |
| `/stats [user] [start_date] [end_date]` | Everyone (Restricted to `STATS_CHANNEL_ID` if set) | Displays an interactive voice dashboard with donut chart & channel bar chart for yourself or a target member. |
| `/leaderboard [start_date] [end_date]` | Everyone (Restricted to `STATS_CHANNEL_ID` if set) | Displays the top 10 most active voice members with timeframe dropdown filter and refresh button. |
| `/rolestats <role> [start_date] [end_date]` | Administrator or Allowed Roles (`.env`) | Generates a paginated activity report for all members of a role (Active/Inactive filters) and attaches a detailed `.csv` spreadsheet. |
| `/report` | Everyone (Restricted to `STATS_CHANNEL_ID` if set) | Generates and sends a downloadable `.csv` voice report for the current month. |

### Command Options:
* `start_date` / `end_date`: Custom date in `YYYY-MM-DD` format (e.g., `2026-09-01` to `2026-09-15`). If left blank, commands default to the current month.
* `role`: Select any server role (e.g. `@labelers`) from the autocomplete menu.

---

## 🛠️ Prerequisites

1. **Python**: Version `3.10` or higher.
2. **Discord Bot Token**: Create an application on the [Discord Developer Portal](https://discord.com/developers/applications).
3. **Privileged Gateway Intents** (Required):
   * Go to **Bot** tab in the Developer Portal.
   * Enable ✅ **Server Members Intent** (required to read role members).
   * Enable ✅ **Voice States Intent** (required to track voice channels).

---

## ⚙️ Environment Variables Configuration (`.env`)

Create a `.env` file in the root directory (see `.env.example`):

```env
# Discord Bot Token (Required)
DISCORD_TOKEN=your_bot_token_here

# Channel Restrictions & Alerts (Optional)
REPORT_CHANNEL_ID=1473963048028082227   # Private admin channel for monthly automated CSV
STATS_CHANNEL_ID=1550433774972698674    # Public channel to restrict /stats, /leaderboard, /report
AFK_CHANNEL_ID=1473963047532892262      # Voice channel ID where deafened users are moved

# Role-Based Permissions for /rolestats (Optional)
# Comma-separated Role IDs or Role Names authorized to run /rolestats (Admins always have access)
ROLESTATS_ALLOWED_ROLES=1473963046396494021,1474690818387349514

# Local Timezone (Standard IANA Name)
TIMEZONE=Asia/Dhaka

# SQLite Database Filename (Optional)
DB_FILE=voice_stats.db
```

---

## 🚀 Setup & Installation Guide

### Option A: Ubuntu VPS (24/7 Hosting with Auto-Restart)

#### Step 1: Update System & Install Dependencies
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
> *Tip: If prompted for GitHub authentication, use your GitHub username and a [Personal Access Token (PAT)](https://github.com/settings/tokens) as the password.*

#### Step 3: Create Virtual Environment & Install Requirements
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 4: Configure Your `.env`
```bash
cp .env.example .env
nano .env
```
Paste your Bot Token, Channel IDs, and Allowed Roles, then save with `Ctrl + O`, `Enter`, and exit with `Ctrl + X`.

#### Step 5: Configure 24/7 Systemd Service
Create the service configuration:
```bash
sudo nano /etc/systemd/system/counterbot.service
```

Paste the following configuration (replace `your-username` with your VPS username):
```ini
[Unit]
Description=Discord Voice Counter Bot v2.0
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

Save and exit (`Ctrl + O`, `Enter`, `Ctrl + X`).

#### Step 6: Start & Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable counterbot.service
sudo systemctl start counterbot.service
```

#### Step 7: Check Live Status & Logs
```bash
# Check service status
sudo systemctl status counterbot.service

# View live runtime logs
sudo journalctl -u counterbot.service -f
```

---

### Option B: Local Setup (Windows / macOS / Linux)

1. Clone or download the repository:
   ```bash
   git clone https://github.com/Iam-sadman/Discord-Time-Counter-Bot.git
   cd Discord-Time-Counter-Bot
   ```
2. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your credentials:
   ```bash
   cp .env.example .env
   ```
5. Run the bot:
   ```bash
   python bot.py
   ```

---

## 🔄 Updating to Latest Version on VPS

Whenever changes are pushed to GitHub, update your VPS with:

```bash
cd ~/Discord-Time-Counter-Bot
git pull
sudo systemctl restart counterbot
sudo journalctl -u counterbot -n 15
```

---

## 📜 License

Distributed under the MIT License. See `license.md` for more information.