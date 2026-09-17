🎙️ Discord Voice Counter Bot
A asynchronous Discord bot built with discord.py and aiosqlite that tracks user voice channel engagement (unmuted, muted, and deafened times), generates detailed CSV reports, and automates monthly database resets.
✨ Features
⏱️ Granular Voice Tracking: Differentiates between Unmuted, Muted, and Deafened states per user for each voice channel.
📅 Automated Monthly Reset: Automatically generates a CSV report and resets data on the last day of every month at 23:59 (Asia/Dhaka timezone).
📊 /report Command: Generates a current mid-month CSV report at any time without resetting stored statistics.
🧹 /resetdata Command: Administrator-restricted slash command to manually clear recorded activity.
💾 SQLite Async Database: Efficient local data storage using non-blocking aiosqlite.
⚡ VPS Ready: Configured for 24/7 systemd background deployment with auto-restart on system reboot.
📋 Prerequisites
Python: Version 3.10 or higher
Discord Bot Token: Created via the Discord Developer Portal
Privileged Gateway Intents:
Server Members Intent
Voice States Intent
📁 Project Structure
counter_bot/
├── bot.py              # Main Python script containing bot logic
└── README.md           # Project documentation


⚙️ Environment Variables
Create a .env file in the root directory with the following variables:
DISCORD_TOKEN=your_discord_bot_token_here
REPORT_CHANNEL_ID=your_text_channel_id_here
TIMEZONE=Asia/Dhaka


🚀 Setup & Installation
1. Clone the Repository
git clone https://github.com/your-username/discord-voice-counter-bot.git
cd discord-voice-counter-bot


2. Create and Activate Virtual Environment
python3 -m venv .venv
source .venv/bin/activate


3. Install Dependencies
pip install -r requirements.txt


4. Discord Developer Portal Settings
Go to Discord Developer Portal and open your app.
Navigate to Bot tab and turn ON:
✅ Server Members Intent
✅ Voice States Intent
Navigate to OAuth2 ➔ URL Generator:
Select Scopes: bot, applications.commands
Select Bot Permissions: View Channels, Send Messages, Attach Files, Connect
Copy the generated URL to invite the bot to your target server.
🛠️ Usage
Run Manually
python bot.py


Available Slash Commands
Command
Permission Required
Description
/report
Everyone
Generates and sends a CSV report without clearing stored data.
/resetdata
Administrator
Clears all recorded voice activity statistics from the database.

🖥️ VPS Deployment (Linux Systemd)
To keep the bot running 24/7 on Ubuntu/Debian and launch automatically on reboot:
Create a systemd service file:
sudo nano /etc/systemd/system/counterbot.service


Paste the following configuration (update paths and username as needed):
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


Enable and start the service:
sudo systemctl daemon-reload
sudo systemctl enable --now counterbot


Verify service status:
sudo systemctl status counterbot


📄 Helper Files Reference
requirements.txt
discord.py
aiosqlite
pandas
python-dotenv


.gitignore
.env
*.db
.venv/
__pycache__/
*.csv


📜 License
Distributed under the MIT License.
