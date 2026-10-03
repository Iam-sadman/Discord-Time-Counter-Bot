"""
cogs/leaderboard.py — Voice Leaderboard, Cutoff History, and Persistent Dynamic Live Leaderboards.

Features:
  - /leaderboard [start_date] [end_date] — Interactive voice activity leaderboard with Cutoff & Timeframe selectors.
  - /cutoff_history [category] [part] [month] [year] — Browse any past or current Cutoff leaderboard with pagination.
  - /setup_live_leaderboard [channel] — Deploys permanent, self-updating Voice & ECODA leaderboards with
    interactive [ ◀️ Prev ], [ Next ▶️ ], [ ⏳ Current Cutoff ], and [ ⏪ Previous Cutoff ] buttons.
  - Background task (every 5 minutes) keeping both live boards synchronized and auto-resetting each cutoff.
"""

from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import (
    LOCAL_TZ,
    STATS_CHANNEL_ID,
    build_live_ecoda_leaderboard_embed,
    build_live_voice_leaderboard_embed,
    fetch_ecoda_leaderboard_data,
    fetch_leaderboard_data,
    format_duration,
    format_hours,
    get_cutoff_dates,
    get_date_range,
    get_specific_cutoff_range,
    parse_custom_date,
    resolve_member_display,
    set_setting,
    sync_all_sessions,
    update_live_leaderboard_messages,
    LiveVoiceLeaderboardView,
    LiveEcodaLeaderboardView,
)

PAGE_SIZE = 10


# ==========================================
# INTERACTIVE LEADERBOARD VIEW
# ==========================================
class LeaderboardView(discord.ui.View):
    def __init__(self, start_date: str = None, end_date: str = None, is_custom: bool = False):
        super().__init__(timeout=300)
        self.current_filter = "current_cutoff" if not is_custom else "custom"
        self.start_date = start_date
        self.end_date = end_date
        self.is_custom = is_custom

        if not is_custom:
            for option in self.timeframe_select.options:
                option.default = (option.value == self.current_filter)

    @discord.ui.select(
        placeholder="Select Timeframe / Cutoff...",
        options=[
            discord.SelectOption(label="Current Cutoff", value="current_cutoff", description="Active cutoff period (1-15 or 16-End)", emoji="⏳"),
            discord.SelectOption(label="Previous Cutoff", value="previous_cutoff", description="Preceding cutoff period", emoji="⏪"),
            discord.SelectOption(label="Today", value="today", description="Today's leaderboard", emoji="☀️"),
            discord.SelectOption(label="This Week", value="this_week", description="This week's leaderboard", emoji="📅"),
            discord.SelectOption(label="This Month", value="this_month", description="Current month leaderboard", emoji="🟢"),
            discord.SelectOption(label="Last Month", value="last_month", description="Previous month leaderboard", emoji="🟡"),
            discord.SelectOption(label="This Year", value="this_year", description="Current year leaderboard", emoji="📆"),
            discord.SelectOption(label="All Time", value="all_time", description="Cumulative leaderboard", emoji="🔵"),
        ],
    )
    async def timeframe_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_filter = select.values[0]
        self.is_custom = False
        self.start_date, self.end_date = get_date_range(self.current_filter)

        for option in select.options:
            option.default = (option.value == self.current_filter)

        await interaction.response.defer()
        await render_leaderboard(interaction, self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await sync_all_sessions()
        await interaction.response.defer()
        await render_leaderboard(interaction, self)


# ==========================================
# RENDER HELPER FOR /leaderboard
# ==========================================
async def render_leaderboard(interaction: discord.Interaction, view: LeaderboardView):
    """Builds and sends/edits the leaderboard embed."""
    lb_data = await fetch_leaderboard_data(view.start_date, view.end_date, limit=10)

    filter_labels = {
        "current_cutoff": "⏳ Current Cutoff",
        "previous_cutoff": "⏪ Previous Cutoff",
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

    embed = discord.Embed(
        title="🏆 Server Voice Leaderboard",
        description=f"**Timeframe:** `{label}`\n**Range:** `{date_str}`\n\n",
        color=discord.Color.gold(),
    )

    if not lb_data:
        embed.description += "ℹ️ *No voice activity recorded for this timeframe yet.*"
    else:
        medals = ["🥇", "🥈", "🥉"]
        for idx, entry in enumerate(lb_data[:10], start=1):
            rank_str = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
            name = entry["user_name"]
            total_str = format_duration(entry["total"])
            unmuted_str = format_duration(entry["unmuted"])
            muted_str = format_duration(entry["muted"])
            deafened_str = format_duration(entry["deafened"])
            primary_vc = entry["primary_channel"]

            line = (
                f"{rank_str} **{name}** — `{total_str}`\n"
                f"└ 🔊 `{primary_vc}` | 🟢 `{unmuted_str}` | 🟡 `{muted_str}` | 🔴 `{deafened_str}`\n"
            )
            embed.description += line

    embed.set_footer(text="Showing Top 10 Most Active Voice Members")

    if interaction.response.is_done():
        await interaction.edit_original_response(content="", embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view)


# ==========================================
# CUTOFF HISTORY INTERACTIVE VIEW
# ==========================================
class CutoffHistoryView(discord.ui.View):
    def __init__(
        self,
        category: str,
        start_date: str,
        end_date: str,
        cutoff_label: str,
        page: int = 1,
    ):
        super().__init__(timeout=300)
        self.category = category
        self.start_date = start_date
        self.end_date = end_date
        self.cutoff_label = cutoff_label
        self.page = page
        self.total_pages = 1
        self.cached_data: list[dict] = []

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
        await interaction.response.defer()
        await render_cutoff_history(interaction, self)

    @discord.ui.button(label="📄 1 / 1", style=discord.ButtonStyle.secondary, disabled=True)
    async def indicator_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages:
            self.page += 1
        await interaction.response.defer()
        await render_cutoff_history(interaction, self)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await render_cutoff_history(interaction, self)


async def render_cutoff_history(interaction: discord.Interaction, view: CutoffHistoryView):
    """Renders the paginated historical cutoff embed."""
    if view.category == "voice":
        data = await fetch_leaderboard_data(view.start_date, view.end_date, limit=500)
        title = "📜 Voice Activity Cutoff History"
        color = discord.Color.gold()
    else:
        data = await fetch_ecoda_leaderboard_data(start_date=view.start_date, end_date=view.end_date, limit=500)
        title = "📜 ECODA Work Hours Cutoff History"
        color = discord.Color.teal()

    view.cached_data = data
    total_items = len(data)
    view.total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    view.page = min(max(1, view.page), view.total_pages)

    view.prev_button.disabled = (view.page <= 1)
    view.next_button.disabled = (view.page >= view.total_pages)
    view.indicator_button.label = f"📄 {view.page} / {view.total_pages}"

    embed = discord.Embed(
        title=title,
        description=(
            f"📅 **Cutoff Period:** `{view.cutoff_label}` ({view.start_date} to {view.end_date})\n"
            f"👥 **Total Participants:** `{total_items}`\n\n"
        ),
        color=color,
    )

    if not data:
        embed.description += "ℹ️ *No activity recorded for this cutoff period.*"
    else:
        start_idx = (view.page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_entries = data[start_idx:end_idx]

        medals = ["🥇", "🥈", "🥉"]
        for rank, item in enumerate(page_entries, start=start_idx + 1):
            rank_str = medals[rank - 1] if rank <= 3 else f"`#{rank}`"

            if view.category == "voice":
                name = item["user_name"]
                total_str = format_duration(item["total"])
                unmuted_str = format_duration(item["unmuted"])
                muted_str = format_duration(item["muted"])
                primary_vc = item.get("primary_channel", "None")

                line = (
                    f"{rank_str} **{name}** — `{total_str}`\n"
                    f"└ 🔊 `{primary_vc}` | 🟢 `{unmuted_str}` | 🟡 `{muted_str}`\n"
                )
            else:
                ecoda_name = item["ecoda_name"]
                user_id = item["user_id"]
                role_type = item["role_type"]
                total_hours = item["total_hours"]
                active_days = item["active_days"]
                team_name = item.get("team_name")
                team_badge = f" `[{team_name}]`" if team_name else ""

                display_name, _ = resolve_member_display(interaction.guild, ecoda_name, user_id)
                time_formatted = format_hours(total_hours)
                role_badge = "🏷️ Labeler" if role_type == 0 else "🔍 Checker"
                days_str = f"{active_days}d"

                line = f"{rank_str} {display_name}{team_badge} — **`{time_formatted}`** (`{role_badge}` • `{days_str}`)\n"

            embed.description += line

    embed.set_footer(text=f"Page {view.page} of {view.total_pages} • Total: {total_items} records")

    if interaction.response.is_done():
        await interaction.edit_original_response(content="", embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view)


# ==========================================
# COG
# ==========================================
class LeaderboardCog(commands.Cog):
    """Cog providing voice leaderboard, cutoff history, and persistent live leaderboards."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.live_leaderboards_task.start()

    def cog_unload(self):
        self.live_leaderboards_task.cancel()

    # ------------------------------------------
    # BACKGROUND TASK: Auto-refresh live boards every 5 mins
    # ------------------------------------------
    @tasks.loop(minutes=5)
    async def live_leaderboards_task(self):
        await self.bot.wait_until_ready()
        try:
            await sync_all_sessions()
            await update_live_leaderboard_messages(self.bot)
        except Exception as e:
            print(f"Notice: Failed to update live leaderboards in background: {e}")

    # ------------------------------------------
    # SLASH COMMAND: /leaderboard
    # ------------------------------------------
    @app_commands.command(name="leaderboard", description="View the top active voice channel members.")
    @app_commands.describe(
        start_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-01)",
        end_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-15)",
    )
    async def leaderboard_command(
        self,
        interaction: discord.Interaction,
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
        await sync_all_sessions()

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
            final_start, final_end = get_date_range("current_cutoff")

        view = LeaderboardView(start_date=final_start, end_date=final_end, is_custom=is_custom)
        await render_leaderboard(interaction, view)

    # ------------------------------------------
    # SLASH COMMAND: /cutoff_history
    # ------------------------------------------
    @app_commands.command(
        name="cutoff_history",
        description="Inspect any historical Cutoff leaderboard (Voice Activity or ECODA Work Hours).",
    )
    @app_commands.describe(
        category="Select Voice Activity or ECODA Work Hours",
        part="Choose 1st Cutoff (1st-15th) or 2nd Cutoff (16th-End)",
        month="Month number (1 to 12, defaults to current month)",
        year="Year (e.g. 2026, defaults to current year)",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="🔊 Voice Activity Leaderboard", value="voice"),
            app_commands.Choice(name="💼 ECODA Work Hours Leaderboard", value="ecoda"),
        ],
        part=[
            app_commands.Choice(name="1st Cutoff (1st - 15th)", value=1),
            app_commands.Choice(name="2nd Cutoff (16th - End of Month)", value=2),
        ],
    )
    async def cutoff_history(
        self,
        interaction: discord.Interaction,
        category: str,
        part: int,
        month: int | None = None,
        year: int | None = None,
    ):
        now_local = datetime.now(LOCAL_TZ)
        tgt_year = year or now_local.year
        tgt_month = month or now_local.month

        if not (1 <= tgt_month <= 12):
            await interaction.response.send_message("❌ Month must be between 1 and 12.", ephemeral=True)
            return

        if not (2020 <= tgt_year <= 2050):
            await interaction.response.send_message("❌ Please enter a valid year (e.g. 2026).", ephemeral=True)
            return

        await interaction.response.defer()
        if category == "voice":
            await sync_all_sessions()

        start_date, end_date, cutoff_label = get_specific_cutoff_range(tgt_year, tgt_month, part)
        view = CutoffHistoryView(
            category=category,
            start_date=start_date,
            end_date=end_date,
            cutoff_label=cutoff_label,
            page=1,
        )
        await render_cutoff_history(interaction, view)

    # ------------------------------------------
    # SLASH COMMAND: /setup_live_leaderboard
    # ------------------------------------------
    @app_commands.command(
        name="setup_live_leaderboard",
        description="Deploy persistent live dynamic Voice & ECODA leaderboards with next/prev buttons [Admin only].",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel where both live leaderboards will be posted and updated")
    async def setup_live_leaderboard(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        perms = channel.permissions_for(channel.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await interaction.followup.send(
                f"❌ Bot does not have permissions to send messages or embed links in <#{channel.id}>. Please check bot roles.",
                ephemeral=True,
            )
            return

        try:
            cutoff_mode = "current"
            start_date, end_date, cutoff_label = get_cutoff_dates(cutoff_mode)

            # 1. Post Initial Voice Leaderboard message with interactive view
            voice_data = await fetch_leaderboard_data(start_date, end_date, limit=500)
            voice_embed, act_page, total_pages = build_live_voice_leaderboard_embed(
                channel.guild, voice_data, start_date, end_date, cutoff_label, page=1, page_size=10
            )
            voice_view = LiveVoiceLeaderboardView(page=act_page, total_pages=total_pages, cutoff_mode=cutoff_mode)
            voice_msg = await channel.send(embed=voice_embed, view=voice_view)

            # 2. Post Initial ECODA Leaderboard message with interactive view (default: Labelers & Active)
            ecoda_data = await fetch_ecoda_leaderboard_data(
                start_date=start_date,
                end_date=end_date,
                role_filter=0,
                status_filter="active",
                limit=500,
            )
            ecoda_embed, act_page, total_pages = build_live_ecoda_leaderboard_embed(
                channel.guild,
                ecoda_data,
                start_date,
                end_date,
                cutoff_label,
                role_filter=0,
                status_filter="active",
                page=1,
                page_size=10,
            )
            ecoda_view = LiveEcodaLeaderboardView(
                page=act_page,
                total_pages=total_pages,
                cutoff_mode=cutoff_mode,
                role_filter=0,
                status_filter="active",
            )
            ecoda_msg = await channel.send(embed=ecoda_embed, view=ecoda_view)

            # 3. Save IDs in database settings
            await set_setting("live_leaderboard_channel_id", str(channel.id))
            await set_setting("live_voice_msg_id", str(voice_msg.id))
            await set_setting("live_ecoda_msg_id", str(ecoda_msg.id))

            # 4. Try pinning messages if permitted
            if perms.manage_messages:
                try:
                    await voice_msg.pin(reason="Live Dynamic Voice Leaderboard")
                    await ecoda_msg.pin(reason="Live Dynamic ECODA Leaderboard")
                except Exception:
                    pass

            embed = discord.Embed(
                title="✅ Dynamic Cutoff Live Leaderboards Deployed!",
                description=(
                    f"Both **Voice Leaderboard** and **ECODA Leaderboard** are now live in <#{channel.id}>!\n\n"
                    f"📌 **Key Functionalities Active:**\n"
                    f"• **Cutoff Tracking:** Tracking `{cutoff_label}`. Automatically resets when each cutoff ends.\n"
                    f"• **Interactive Pagination:** Users can click `◀️ Prev` and `Next ▶️` directly on the messages.\n"
                    f"• **Cutoff Toggle:** Users can click `[ ⏳ Current Cutoff ]` and `[ ⏪ Previous Cutoff ]` to switch periods.\n"
                    f"• **History Check:** Anyone can use `/cutoff_history` to check any past cutoff record!\n\n"
                    f"🔒 **Channel Permissions Tip for <#{channel.id}>:**\n"
                    f"Channel Settings ➔ Permissions ➔ `@everyone`:\n"
                    f"• **View Channel:** ✅ `Allow`\n"
                    f"• **Read Message History:** ✅ `Allow`\n"
                    f"• **Send Messages:** ❌ `Deny`"
                ),
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to setup live leaderboards: `{e}`", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
