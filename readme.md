# 🎙️ Discord Voice Counter Bot

An asynchronous Discord bot built with `discord.py`, `aiosqlite`, and `matplotlib` that tracks user voice channel engagement (unmuted, muted, and deafened times), generates rich visual dashboards, provides interactive leaderboards, exports CSV reports, and manages historical statistics seamlessly.

---

## ✨ Key Features

* ⏱️ **Granular Voice Tracking**: Accurately tracks **Unmuted**, **Muted**, and **Deafened** states per user across every voice channel.
* 📊 **Dual-Chart Visual Dashboard (`/stats`)**: Generates an automated dark-themed graphic containing:
  * **Donut Chart**: Proportion of Unmuted vs. Muted vs. Deafened states.
  * **Horizontal Bar Chart**: Top active voice channels and exact durations.
* 🏆 **Voice Leaderboard (`/leaderboard`)**: Displays the Top 10 most active members in the server with rank badges (🥇, 🥈, 🥉), primary voice channels, and detailed state breakdowns.
* 🗓️ **Multi-Timeframe Support**: Filter statistics and leaderboards instantly via Discord UI Select Menus (Today, This Week, This Month, Last Month, This Year, All Time).
* 🔒 **Channel & Admin Security**:
  * `/stats` and `/leaderboard` can be restricted to a dedicated public stats channel (`STATS_CHANNEL_ID`).
  * `/report` and `/resetdata` are secured with administrator permissions.
* 📁 **Automated CSV Reports**: Automatically generates monthly CSV reports and sends them to your designated channel.
* 💾 **Persistent SQLite Storage**: Organizes metrics efficiently with fast indexing.

---

## 📋 Slash Commands Overview

| **Command** | **Target Channel** | **Permission** | **Description** |
| :--- | :--- | :--- | :--- |
| `/stats [user]` | Public Stats Channel | Everyone | Displays an interactive voice dashboard and dual-chart graphic for yourself or a target member. |
| `/leaderboard` | Public Stats Channel | Everyone | Displays the top 10 active voice members with timeframe filtering options. |
| `/report` | Admin Channel / Public | Administrator | Manually generates and sends a current month `.csv` voice activity report. |
| `/resetdata` | Admin Channel / Public | Administrator | Permanently clears all recorded voice activity statistics from the database. |

---

## 🛠️ Prerequisites

* **Python**: Version `3.10` or higher
* **Discord Bot Token**: Created via the [Discord Developer Portal](https://discord.com/developers/applications)
* **Privileged Gateway Intents**:
  * ✅ **Server Members Intent**
  * ✅ **Voice States Intent**

---

## ⚙️ Environment Variables (`.env`)

Create a `.env` file in the root directory of your project:

```env
DISCORD_TOKEN=your_discord_bot_token_here
REPORT_CHANNEL_ID=123456789012345678   # Private Admin Channel ID for reports
STATS_CHANNEL_ID=987654321098765432    # Public Text Channel ID for /stats and /leaderboard
AFK_CHANNEL_ID=111222333444555666      # Optional: AFK channel ID for auto-move features
TIMEZONE=Asia/Dhaka
```

---

## 🚀 Setup & Installation on Ubuntu VPS (24/7 Hosting + Auto-Restart)

Follow these step-by-step instructions to set up your bot on an Ubuntu VPS so that it runs 24/7 in the background and automatically restarts whenever the VPS reboots.

### Step 1: Update System & Install Dependencies
Connect to your VPS via SSH and update your system packages:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv git -y
```

### Step 2: Clone or Upload Your Bot Files
Navigate to your preferred directory (e.g., `/home/username/`) and clone your repository, or create your project folder:
```bash
cd ~
git clone https://github.com/your-username/discord-voice-counter-bot.git
cd discord-voice-counter-bot
```

### Step 3: Create Python Virtual Environment & Install Requirements
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

*(Ensure your `requirements.txt` contains: `discord.py`, `aiosqlite`, `matplotlib`, `python-dotenv`)*

### Step 4: Configure Your `.env` File
Create and populate your `.env` configuration file:
```bash
nano .env
```
Paste your configuration, save, and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

### Step 5: Configure Systemd Service for 24/7 Uptime & Auto-Restart on Reboot

To keep your bot running continuously in the background and ensure it restarts automatically if the VPS restarts, create a systemd service.

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/counterbot.service
   ```

2. Paste the following configuration (replace `your-username` and paths with your actual VPS username and project path):
   ```ini
   [Unit]
   Description=Discord Voice Counter Bot Service
   After=network.target

   [Service]
   Type=simple
   User=your-username
   WorkingDirectory=/home/your-username/discord-voice-counter-bot
   ExecStart=/home/your-username/discord-voice-counter-bot/.venv/bin/python /home/your-username/discord-voice-counter-bot/bot.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. Save and exit the file (`Ctrl+O`, `Enter`, `Ctrl+X`).

### Step 6: Enable and Start the Bot Service
Run the following commands to register, enable, and start your bot service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable counterbot.service
sudo systemctl start counterbot.service
```

### Step 7: Check Bot Status & Logs
To verify that your bot is running smoothly and active 24/7:
```bash
sudo systemctl status counterbot.service
```

To view live runtime logs (helpful for debugging):
```bash
sudo journalctl -u counterbot.service -f
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.