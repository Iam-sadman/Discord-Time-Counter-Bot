🎙️ Discord Voice Counter Bot

An asynchronous Discord bot built with discord.py, aiosqlite, and matplotlib that tracks user voice channel engagement (unmuted, muted, and deafened times), generates rich visual dashboards, provides interactive leaderboards, exports CSV reports, and manages multi-month historical statistics seamlessly.

✨ Key Features

⏱️ Granular Voice Tracking: Accurately tracks Unmuted, Muted, and Deafened states per user across every voice channel.

📊 Dual-Chart Visual Dashboard (/stats): Generates an automated dark-themed graphic containing:

Donut Chart: Proportion of Unmuted vs. Muted vs. Deafened states.

Horizontal Bar Chart: Top active voice channels and exact durations.

🏆 Voice Leaderboard (/leaderboard): Displays the Top 10 most active members in the server with rank badges (🥇, 🥈, 🥉), primary voice channels, and detailed state breakdowns.

🗓️ Multi-Timeframe Support: Filter statistics and leaderboards instantly via Discord UI Select Menus:

🟢 This Month

🟡 Last Month

🔵 All Time

🔒 Channel & Admin Security:

/stats and /leaderboard are restricted to a dedicated public stats channel (STATS_CHANNEL_ID).

/report and /resetdata are restricted to Administrator permissions and a private admin channel (REPORT_CHANNEL_ID).

📁 Automated CSV Reports: Automatically generates a monthly CSV report and sends it to the admin channel on the last day of every month at 23:59 without deleting historical database records.

💾 Persistent SQLite Storage: Organizes metrics using YYYY-MM month tags for high-performance querying without dataset degradation.

📋 Slash Commands Overview

Command

Target Channel

Permission

Description

/stats [user]

Public Stats Channel

Everyone

Displays an interactive voice dashboard and dual-chart graphic for yourself or a target member.

/leaderboard

Public Stats Channel

Everyone

Displays the top 10 active voice members with timeframe filtering options.

/report

Private Admin Channel

Administrator

Generates and sends a current month .csv report without wiping database records.

/resetdata

Private Admin Channel

Administrator

Permanently clears all recorded voice activity statistics from the database.

🛠️ Prerequisites

Python: Version 3.10 or higher

Discord Bot Token: Created via the Discord Developer Portal

Privileged Gateway Intents:

✅ Server Members Intent

✅ Voice States Intent

⚙️ Environment Variables (.env)

Create a .env file in the root directory of the project:

DISCORD_TOKEN=your_discord_bot_token_here
REPORT_CHANNEL_ID=123456789012345678   # Private Admin Channel ID for reports
STATS_CHANNEL_ID=987654321098765432    # Public Text Channel ID for /stats and /leaderboard
TIMEZONE=Asia/Dhaka


🚀 Setup & Installation

1. Clone the Repository

git clone https://github.com/your-username/discord-voice-counter-bot.git
cd discord-voice-counter-bot


2. Create Virtual Environment & Install Dependencies

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt


3. Requirements (requirements.txt)

Ensure your requirements.txt contains:

discord.py
aiosqlite
matplotlib
python-dotenv


🖥️ 24/7 VPS Deployment (Systemd Service)

To run the bot continuously in the background on Ubuntu/Debian:

Create a service file:

sudo nano /etc/systemd/system/counterbot.service


Add the following service configuration:

[Unit]
Description=Discord Voice Counter Bot Service
After=network.target

[Service]
User=gekiye
WorkingDirectory=/home/gekiye/Downloads/counter_bot
ExecStart=/home/gekiye/Downloads/counter_bot/.venv/bin/python /home/gekiye/Downloads/counter_bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target


Reload daemon, enable, and start service:

sudo systemctl daemon-reload
sudo systemctl enable --now counterbot


Check bot operational status:

sudo systemctl status counterbot


📜 License

Distributed under the MIT License. See LICENSE for more information.
