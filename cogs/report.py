"""
cogs/report.py — /report command for manual CSV generation.

Provides:
  - /report  — generates current month's voice report CSV
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    STATS_CHANNEL_ID,
    generate_and_send_csv,
)


class ReportCog(commands.Cog):
    """Cog providing the /report slash command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="report", description="Manually generate the current month's voice report CSV.")
    async def report_command(self, interaction: discord.Interaction):
        if STATS_CHANNEL_ID and interaction.channel_id != STATS_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{STATS_CHANNEL_ID}>",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        await generate_and_send_csv(interaction, "this_month")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReportCog(bot))
