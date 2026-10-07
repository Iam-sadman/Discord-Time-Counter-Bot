"""
bot.py — Entry point for the Discord Voice Counter Bot.

Responsibilities:
  - Create the bot instance with required intents
  - Load the database and all cogs in setup_hook
  - Scan existing voice sessions on startup (on_ready)
  - Register a global app_command error handler
  - Run the bot

All logic is split across:
  utils.py            — config, shared state, DB ops, helpers, chart/CSV generators
  cogs/voice_tracking.py — on_voice_state_update + background tasks
  cogs/stats.py       — /stats command + DashboardView
  cogs/leaderboard.py — /leaderboard command + LeaderboardView
  cogs/report.py      — /report command
  cogs/rolestats.py   — /rolestats command + RoleStatsView
"""

import time

import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    BOT_TOKEN,
    LOCAL_TZ,
    ROLESTATS_ALLOWED_ROLES,
    active_sessions,
    determine_state,
    init_db,
    LiveVoiceLeaderboardView,
    LiveEcodaLeaderboardView,
    LiveTeamUploadStatusView,
)

# ==========================================
# BOT CLASS
# ==========================================
COGS = [
    "cogs.voice_tracking",
    "cogs.stats",
    "cogs.leaderboard",
    "cogs.report",
    "cogs.rolestats",
    "cogs.ecoda",
]


class VoiceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Called once before the bot connects. Load DB, cogs, persistent views, and sync slash commands."""
        await init_db()

        # Register persistent views for live leaderboards
        self.add_view(LiveVoiceLeaderboardView())
        self.add_view(LiveEcodaLeaderboardView())
        self.add_view(LiveTeamUploadStatusView())

        for cog in COGS:
            await self.load_extension(cog)
            print(f"✅ Loaded cog: {cog}")

        await self.tree.sync()
        print("✅ Slash commands synced.")


bot = VoiceBot()


# ==========================================
# STARTUP EVENT
# ==========================================
@bot.event
async def on_ready():
    """Scan any members already in voice channels when the bot starts/restarts."""
    print(f"✅ Logged in as {bot.user}")
    allowed_ids = list(ROLESTATS_ALLOWED_ROLES["ids"])
    allowed_names = list(ROLESTATS_ALLOWED_ROLES["names"])
    print(f"ℹ️ /rolestats allowed roles: IDs={allowed_ids} | Names={allowed_names}")

    now = time.time()
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot or not member.voice or not member.voice.channel:
                continue
            if member.id not in active_sessions:
                state = determine_state(member.voice)
                active_sessions[member.id] = {
                    "channel_id": member.voice.channel.id,
                    "channel_name": member.voice.channel.name,
                    "last_channel_name": "None",
                    "join_timestamp": now,
                    "state": state,
                    "last_update": now,
                    "name": member.display_name,
                }
    print("✅ Existing voice sessions scanned and initialized.")


# ==========================================
# GLOBAL ERROR HANDLER
# ==========================================
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ You need Administrator permissions to use this command."
    else:
        print(f"Command Error: {error}")
        msg = f"❌ Command process korte somossa hoyeche: `{error}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


# ==========================================
# ENTRYPOINT
# ==========================================
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
