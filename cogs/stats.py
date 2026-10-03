"""
cogs/stats.py — /stats command with interactive DashboardView.

Provides:
  - /stats [user] [start_date] [end_date]  — interactive per-user voice dashboard
"""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    STATS_CHANNEL_ID,
    LOCAL_TZ,
    active_sessions,
    last_connected_channels,
    format_duration,
    get_date_range,
    parse_custom_date,
    fetch_user_stats,
    generate_stats_chart_sync,
    flush_user_session,
)


# ==========================================
# DASHBOARD VIEW (interactive UI)
# ==========================================
class DashboardView(discord.ui.View):
    def __init__(self, target_member: discord.Member, start_date: str = None, end_date: str = None, is_custom: bool = False):
        super().__init__(timeout=300)
        self.target_member = target_member
        self.current_filter = "this_month" if not is_custom else "custom"
        self.start_date = start_date
        self.end_date = end_date
        self.is_custom = is_custom

        if not is_custom:
            for option in self.children[0].options:
                option.default = (option.value == self.current_filter)

    @discord.ui.select(
        placeholder="Select Timeframe...",
        options=[
            discord.SelectOption(label="Today", value="today", description="Today's stats", emoji="☀️"),
            discord.SelectOption(label="This Week", value="this_week", description="This week's stats", emoji="📅"),
            discord.SelectOption(label="This Month", value="this_month", description="Current month stats", emoji="🟢"),
            discord.SelectOption(label="Last Month", value="last_month", description="Previous month stats", emoji="🟡"),
            discord.SelectOption(label="This Year", value="this_year", description="Current year stats", emoji="📆"),
            discord.SelectOption(label="All Time", value="all_time", description="Cumulative stats", emoji="🔵"),
        ],
    )
    async def select_timeframe(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_filter = select.values[0]
        self.is_custom = False
        self.start_date, self.end_date = get_date_range(self.current_filter)

        for option in select.options:
            option.default = (option.value == self.current_filter)

        await interaction.response.defer()
        await render_dashboard(interaction, self.target_member, self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await flush_user_session(self.target_member.id)
        await interaction.response.defer()
        await render_dashboard(interaction, self.target_member, self)


# ==========================================
# RENDER HELPER
# ==========================================
async def render_dashboard(interaction: discord.Interaction, member: discord.Member, view: DashboardView):
    """Builds and sends/edits the stats embed with chart."""
    stats = await fetch_user_stats(member.id, view.start_date, view.end_date)
    chart_buf = await asyncio.to_thread(generate_stats_chart_sync, stats, stats["channel_breakdown"])

    filter_labels = {
        "today": "☀️ Today",
        "this_week": "📅 This Week",
        "this_month": "🟢 This Month",
        "last_month": "🟡 Last Month",
        "this_year": "📆 This Year",
        "all_time": "🔵 All Time",
        "custom": "🔧 Custom Range",
    }

    label = filter_labels.get(view.current_filter, "🔧 Custom Range")
    date_str = (
        f"({view.start_date} to {view.end_date})"
        if view.start_date != view.end_date
        else f"({view.start_date})"
    )

    # Live session data
    session = active_sessions.get(member.id)
    if session and session.get("channel_id") and session.get("join_timestamp"):
        from datetime import datetime
        current_vc = session.get("channel_name", "Not in Voice") or "Not in Voice"
        join_ts = session.get("join_timestamp")
        join_time_formatted = datetime.fromtimestamp(join_ts, LOCAL_TZ).strftime("%I:%M %p") if join_ts else "N/A"
    else:
        current_vc = "Not in Voice"
        join_time_formatted = "N/A"

    last_vc = last_connected_channels.get(member.id) or (session.get("last_channel_name") if session else None) or "None"

    embed = discord.Embed(
        title=f"🎙️ Voice Dashboard — {member.display_name}",
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)

    # Row 1
    embed.add_field(name="⏳ Timeframe", value=f"`{label}`\n`{date_str}`", inline=True)
    embed.add_field(name="⏱️ Total Voice Time", value=f"`{format_duration(stats['total'])}`", inline=True)
    embed.add_field(name="🔊 Primary Channel", value=f"`{stats['top_vc'] or 'None'}`", inline=True)

    # Row 2
    embed.add_field(name="🎧 Current VC", value=f"`{current_vc}`", inline=True)
    embed.add_field(name="⏰ Join Time", value=f"`{join_time_formatted}`", inline=True)
    embed.add_field(name="↩️ Last Connected VC", value=f"`{last_vc}`", inline=True)

    # Row 3
    embed.add_field(
        name="📊 Detailed Breakdown",
        value=(
            f"🟢 **Unmuted:** {format_duration(stats['unmuted'])}\n"
            f"🟡 **Muted:** {format_duration(stats['muted'])}\n"
            f"🔴 **Deafened:** {format_duration(stats['deafened'])}"
        ),
        inline=False,
    )
    embed.set_image(url="attachment://stats_chart.png")

    file = discord.File(fp=chart_buf, filename="stats_chart.png")

    if interaction.response.is_done():
        await interaction.edit_original_response(content="", embed=embed, attachments=[file], view=view)
    else:
        await interaction.followup.send(embed=embed, file=file, view=view)


# ==========================================
# COG
# ==========================================
class StatsCog(commands.Cog):
    """Cog providing the /stats slash command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View interactive voice activity dashboard for yourself or another user.")
    @app_commands.describe(
        user="Select a user to view their stats (leave blank for yourself)",
        start_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-01)",
        end_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-15)",
    )
    async def stats_command(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        start_date: str = None,
        end_date: str = None,
    ):
        if STATS_CHANNEL_ID and interaction.channel_id != STATS_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ This command can only be used in <#{STATS_CHANNEL_ID}>",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        target_member = user or interaction.user
        if target_member.id in active_sessions:
            await flush_user_session(target_member.id)

        is_custom = False
        parsed_start = parse_custom_date(start_date) if start_date else None
        parsed_end = parse_custom_date(end_date) if end_date else None

        if start_date or end_date:
            if start_date and not parsed_start:
                await interaction.followup.send("❌ `start_date` format thik nei! (Example: 2026-09-01)", ephemeral=True)
                return
            if end_date and not parsed_end:
                await interaction.followup.send("❌ `end_date` format thik nei! (Example: 2026-09-15)", ephemeral=True)
                return

            final_start = parsed_start or parsed_end
            final_end = parsed_end or parsed_start

            if final_start > final_end:
                final_start, final_end = final_end, final_start

            is_custom = True
        else:
            final_start, final_end = get_date_range("this_month")

        view = DashboardView(target_member, start_date=final_start, end_date=final_end, is_custom=is_custom)
        await render_dashboard(interaction, target_member, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
