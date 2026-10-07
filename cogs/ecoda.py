"""
cogs/ecoda.py — ECODA Activity Leaderboard, Daily Work Hours Upload, and Configuration.

Features:
  - /ecoda_upload [file] [date] — Checkers/Team Leaders upload daily CSV or Excel (.xlsx) work hours.
    - Restricted to the designated upload channel (if set by Admin).
    - Matches 'user_name' with Discord nicknames/display names.
    - If matched, links Discord User ID.
    - If unmatched, reports list of unmatched workers and shows their sheet name on the leaderboard.
    - Auto-links dynamically when unmatched users later update their Discord nicknames.
    - Automatically updates the live leaderboard in the dedicated channel.
  - /ecoda_edit [worker] [hours] [date] [note] — Correct/edit hours if duplicate or faulty data was uploaded.
  - /ecoda_set_role [role] — Admin sets the Team Leader / Checker role.
  - /ecoda_set_channel [channel] — Admin sets the designated upload channel.
  - /ecoda_settings — View current ECODA configurations.
  - /ecoda_leaderboard — Interactive leaderboard with Timeframe (Today, Week, Month, All-Time),
    Role filter (All, Labelers, Checkers), and multi-page pagination.
"""

import calendar
from datetime import datetime, timedelta
import re
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    LOCAL_TZ,
    add_ecoda_excluded_worker,
    add_ecoda_manual_record,
    add_team,
    build_team_upload_status_embed,
    delete_ecoda_by_date,
    delete_ecoda_record,
    fetch_ecoda_leaderboard_data,
    fetch_team_upload_status,
    find_member_by_name,
    format_hours,
    get_all_teams,
    get_date_range,
    get_ecoda_excluded_workers,
    get_setting,
    get_team_details_list,
    is_ecoda_checker,
    parse_custom_date,
    parse_ecoda_file,
    remove_ecoda_excluded_worker,
    remove_team,
    reset_ecoda_records,
    resolve_member_display,
    save_ecoda_records,
    set_setting,
    update_ecoda_work_time,
    update_live_leaderboard_messages,
    OnDemandTeamUploadStatusView,
)

PAGE_SIZE = 10


# ==========================================
# INTERACTIVE LEADERBOARD VIEW
# ==========================================
class EcodaLeaderboardView(discord.ui.View):
    def __init__(
        self,
        timeframe: str = "current_cutoff",
        role_filter: int | None = 0,
        status_filter: str = "active",
        page: int = 1,
    ):
        super().__init__(timeout=300)
        self.timeframe = timeframe
        self.role_filter = role_filter
        self.status_filter = status_filter
        self.page = page
        self.total_pages = 1
        self.cached_data: list[dict] = []

        # Sync timeframe select default
        for opt in self.timeframe_select.options:
            opt.default = (opt.value == self.timeframe)

        # Sync role select default
        target_role_val = "all" if role_filter is None else str(role_filter)
        for opt in self.role_select.options:
            opt.default = (opt.value == target_role_val)

        self.btn_active.style = (
            discord.ButtonStyle.success if status_filter == "active" else discord.ButtonStyle.secondary
        )
        self.btn_inactive.style = (
            discord.ButtonStyle.danger if status_filter == "inactive" else discord.ButtonStyle.secondary
        )

    @discord.ui.select(
        placeholder="Select Timeframe / Cutoff...",
        row=0,
        options=[
            discord.SelectOption(label="Current Cutoff", value="current_cutoff", description="Active cutoff period (1-15 or 16-End)", emoji="⏳"),
            discord.SelectOption(label="Previous Cutoff", value="previous_cutoff", description="Preceding cutoff period", emoji="⏪"),
            discord.SelectOption(label="Today", value="today", description="Today's ECODA activity", emoji="☀️"),
            discord.SelectOption(label="This Week", value="this_week", description="This week's ECODA activity", emoji="📅"),
            discord.SelectOption(label="This Month", value="this_month", description="Current month's ECODA activity", emoji="🟢"),
            discord.SelectOption(label="All Time", value="all_time", description="All-time cumulative ECODA activity", emoji="🔵"),
        ],
    )
    async def timeframe_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.timeframe = select.values[0]
        self.page = 1
        for opt in select.options:
            opt.default = (opt.value == self.timeframe)
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)

    @discord.ui.select(
        placeholder="Filter by Role...",
        row=1,
        options=[
            discord.SelectOption(label="Labelers Only", value="0", description="Show and rank only Labelers", emoji="🏷️"),
            discord.SelectOption(label="Checkers Only", value="1", description="Show and rank only Checkers", emoji="🔍"),
            discord.SelectOption(label="All Roles", value="all", description="Show all workers together", emoji="👥"),
        ],
    )
    async def role_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        val = select.values[0]
        self.role_filter = None if val == "all" else int(val)
        self.page = 1
        for opt in select.options:
            opt.default = (opt.value == val)
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)

    @discord.ui.button(label="🟢 Active Members", style=discord.ButtonStyle.success, row=2)
    async def btn_active(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.status_filter = "active"
        self.page = 1
        self.btn_active.style = discord.ButtonStyle.success
        self.btn_inactive.style = discord.ButtonStyle.secondary
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)

    @discord.ui.button(label="🔴 Inactive (0h)", style=discord.ButtonStyle.secondary, row=2)
    async def btn_inactive(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.status_filter = "inactive"
        self.page = 1
        self.btn_active.style = discord.ButtonStyle.secondary
        self.btn_inactive.style = discord.ButtonStyle.danger
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary, row=3)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 1:
            self.page -= 1
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)

    @discord.ui.button(label="📄 1 / 1", style=discord.ButtonStyle.secondary, disabled=True, row=3)
    async def indicator_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary, row=3)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages:
            self.page += 1
        await interaction.response.defer()
        await render_ecoda_leaderboard(interaction, self)


# ==========================================
# RENDER HELPER
# ==========================================
async def render_ecoda_leaderboard(interaction: discord.Interaction, view: EcodaLeaderboardView):
    """Builds and updates the ECODA leaderboard embed and controls."""
    start_date, end_date = get_date_range(view.timeframe)
    data = await fetch_ecoda_leaderboard_data(
        start_date=start_date,
        end_date=end_date,
        role_filter=view.role_filter,
        status_filter=view.status_filter,
        limit=500,
    )
    view.cached_data = data

    total_items = len(data)
    view.total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)
    view.page = min(max(1, view.page), view.total_pages)

    # Update button states
    view.prev_button.disabled = (view.page <= 1)
    view.next_button.disabled = (view.page >= view.total_pages)
    view.indicator_button.label = f"📄 {view.page} / {view.total_pages}"

    # Timeframe and Role label mappings
    tf_labels = {
        "current_cutoff": "⏳ Current Cutoff",
        "previous_cutoff": "⏪ Previous Cutoff",
        "today": "☀️ Today",
        "this_week": "📅 This Week",
        "this_month": "🟢 This Month",
        "all_time": "🔵 All Time",
    }
    role_labels = {
        None: "👥 All Roles",
        0: "🏷️ Labelers Only",
        1: "🔍 Checkers Only",
    }

    tf_str = tf_labels.get(view.timeframe, view.timeframe)
    role_str = role_labels.get(view.role_filter, "All")
    date_str = f"({start_date} to {end_date})" if start_date != end_date else f"({start_date})"

    if view.status_filter == "inactive":
        embed = discord.Embed(
            title=f"💼 ECODA Leaderboard — 🔴 Inactive Members ({role_str})",
            description=(
                f"🔴 **INACTIVE MEMBERS (0 Hours Worked)**\n"
                f"**Timeframe:** `{tf_str}` {date_str}\n"
                f"**Role:** `{role_str}`\n"
                f"**Total Inactive Workers:** `{total_items}`\n"
                f"ℹ️ *Eder ei timeframe e kono work hour record hoyni (0h).*\n\n"
            ),
            color=discord.Color.red(),
        )
    else:
        embed = discord.Embed(
            title=f"💼 ECODA Activity Leaderboard — {role_str}",
            description=(
                f"**Timeframe:** `{tf_str}` {date_str}\n"
                f"**Filter:** `{role_str}` (Separated Rankings)\n"
                f"**Total Active Workers:** `{total_items}`\n\n"
            ),
            color=discord.Color.teal() if view.role_filter == 0 else discord.Color.blue(),
        )

    if not data:
        if view.status_filter == "inactive":
            embed.description += f"🎉 *Shobai active! Ei timeframe e kono inactive worker nei.*"
        else:
            embed.description += "ℹ️ *No ECODA work hours recorded for this timeframe yet.*"
    else:
        start_idx = (view.page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_entries = data[start_idx:end_idx]

        medals = ["🥇", "🥈", "🥉"]
        for idx, item in enumerate(page_entries, start=start_idx + 1):
            ecoda_name = item["ecoda_name"]
            user_id = item["user_id"]
            role_type = item["role_type"]
            total_hours = item["total_hours"]
            active_days = item["active_days"]
            team_name = item.get("team_name")

            display_name, is_matched = resolve_member_display(interaction.guild, ecoda_name, user_id)
            team_badge = f" `[{team_name}]`" if team_name else ""

            if view.status_filter == "inactive":
                line = f"`#{idx}` {display_name}{team_badge} — **`0h 00m`** ⚠️ *Inactive*\n"
            else:
                rank_str = medals[idx - 1] if idx <= 3 else f"`#{idx}`"
                time_formatted = format_hours(total_hours)
                role_badge = "🏷️ Labeler" if role_type == 0 else "🔍 Checker"
                days_str = f"{active_days} day" if active_days == 1 else f"{active_days} days"

                line = (
                    f"{rank_str} {display_name}{team_badge} — **`{time_formatted}`**\n"
                    f"└ `{role_badge}` • 📅 `{days_str}`\n"
                )

            embed.description += line

    status_tag = "Inactive Workers (0h)" if view.status_filter == "inactive" else "Workers"
    embed.set_footer(text=f"Page {view.page} of {view.total_pages} • Total: {total_items} {status_tag}")

    if interaction.response.is_done():
        await interaction.edit_original_response(content="", embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view)


# ==========================================
# INTERACTIVE CALENDAR DATE PICKER VIEW
# ==========================================
class CalendarDatePickerView(discord.ui.View):
    """Interactive Discord Calendar view with month navigation and cutoff day dropdowns."""

    def __init__(
        self,
        author_id: int,
        on_date_selected,  # async callable: (interaction, date_str) -> None
        year: int | None = None,
        month: int | None = None,
    ):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.on_date_selected = on_date_selected

        now = datetime.now(LOCAL_TZ)
        self.year = year or now.year
        self.month = month or now.month
        self.today_str = now.strftime("%Y-%m-%d")
        self.yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        self.setup_components()

    def setup_components(self):
        self.clear_items()
        month_name = calendar.month_name[self.month]
        month_abbr = calendar.month_abbr[self.month]
        last_day = calendar.monthrange(self.year, self.month)[1]

        # Row 0: Navigation Buttons
        btn_prev = discord.ui.Button(label="◀️ Prev", style=discord.ButtonStyle.secondary, row=0)
        btn_prev.callback = self.prev_month
        self.add_item(btn_prev)

        btn_header = discord.ui.Button(
            label=f"📅 {month_name} {self.year}",
            style=discord.ButtonStyle.primary,
            disabled=True,
            row=0,
        )
        self.add_item(btn_header)

        btn_next = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary, row=0)
        btn_next.callback = self.next_month
        self.add_item(btn_next)

        # Row 1: 1st Cutoff Days (Days 1 to min(15, last_day))
        part1_options = []
        for d in range(1, min(16, last_day + 1)):
            dt = datetime(self.year, self.month, d)
            d_str = dt.strftime("%Y-%m-%d")
            weekday = dt.strftime("%a")
            if d_str == self.today_str:
                label = f"☀️ {d:02d} {month_abbr} ({weekday}) — Today"
            elif d_str == self.yesterday_str:
                label = f"⏪ {d:02d} {month_abbr} ({weekday}) — Yesterday"
            else:
                label = f"{d:02d} {month_abbr} ({weekday})"
            part1_options.append(discord.SelectOption(label=label, value=d_str))

        if part1_options:
            select1 = discord.ui.Select(
                placeholder=f"⏳ 1st Cutoff (Days 01-15 {month_abbr})...",
                options=part1_options,
                row=1,
            )
            select1.callback = self.select_day_callback
            self.add_item(select1)

        # Row 2: 2nd Cutoff Days (Days 16 to last_day)
        part2_options = []
        if last_day >= 16:
            for d in range(16, last_day + 1):
                dt = datetime(self.year, self.month, d)
                d_str = dt.strftime("%Y-%m-%d")
                weekday = dt.strftime("%a")
                if d_str == self.today_str:
                    label = f"☀️ {d:02d} {month_abbr} ({weekday}) — Today"
                elif d_str == self.yesterday_str:
                    label = f"⏪ {d:02d} {month_abbr} ({weekday}) — Yesterday"
                else:
                    label = f"{d:02d} {month_abbr} ({weekday})"
                part2_options.append(discord.SelectOption(label=label, value=d_str))

        if part2_options:
            select2 = discord.ui.Select(
                placeholder=f"⏳ 2nd Cutoff (Days 16-{last_day} {month_abbr})...",
                options=part2_options,
                row=2,
            )
            select2.callback = self.select_day_callback
            self.add_item(select2)

        # Row 3: Quick Action Buttons
        btn_today = discord.ui.Button(
            label=f"☀️ Today ({self.today_str[-5:]})",
            style=discord.ButtonStyle.success,
            row=3,
        )
        btn_today.callback = self.quick_today
        self.add_item(btn_today)

        btn_yesterday = discord.ui.Button(
            label=f"⏪ Yesterday ({self.yesterday_str[-5:]})",
            style=discord.ButtonStyle.secondary,
            row=3,
        )
        btn_yesterday.callback = self.quick_yesterday
        self.add_item(btn_yesterday)

        btn_cancel = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=3)
        btn_cancel.callback = self.cancel_callback
        self.add_item(btn_cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This date picker belongs to another user.", ephemeral=True
            )
            return False
        return True

    async def prev_month(self, interaction: discord.Interaction):
        if self.month == 1:
            self.month = 12
            self.year -= 1
        else:
            self.month -= 1
        self.setup_components()
        await interaction.response.edit_message(view=self)

    async def next_month(self, interaction: discord.Interaction):
        if self.month == 12:
            self.month = 1
            self.year += 1
        else:
            self.month += 1
        self.setup_components()
        await interaction.response.edit_message(view=self)

    async def select_day_callback(self, interaction: discord.Interaction):
        values = interaction.data.get("values", [])
        if values:
            for item in self.children:
                item.disabled = True
            await self.on_date_selected(interaction, values[0])

    async def quick_today(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await self.on_date_selected(interaction, self.today_str)

    async def quick_yesterday(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await self.on_date_selected(interaction, self.yesterday_str)

    async def cancel_callback(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Operation cancelled.", embed=None, view=None)


# ==========================================
# INTERACTIVE DELETE PROMPT VIEW
# ==========================================
class EcodaDeletePromptView(discord.ui.View):
    """View offering choices to delete all dates, today, yesterday, or pick from calendar."""

    def __init__(self, author_id: int, on_action):
        super().__init__(timeout=180)
        self.author_id = author_id
        self.on_action = on_action

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ This prompt is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🗑️ Delete ALL Dates", style=discord.ButtonStyle.danger, row=0)
    async def btn_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await self.on_action(interaction, "all")

    @discord.ui.button(label="☀️ Today", style=discord.ButtonStyle.secondary, row=0)
    async def btn_today(self, interaction: discord.Interaction, button: discord.ui.Button):
        now_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        for item in self.children:
            item.disabled = True
        await self.on_action(interaction, now_str)

    @discord.ui.button(label="⏪ Yesterday", style=discord.ButtonStyle.secondary, row=0)
    async def btn_yesterday(self, interaction: discord.Interaction, button: discord.ui.Button):
        yest_str = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
        for item in self.children:
            item.disabled = True
        await self.on_action(interaction, yest_str)

    @discord.ui.button(label="📅 Pick from Calendar", style=discord.ButtonStyle.primary, row=0)
    async def btn_calendar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.on_action(interaction, "calendar")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Deletion cancelled.", embed=None, view=None)


# ==========================================
# INTERACTIVE RESET CONFIRM VIEW
# ==========================================
class EcodaResetConfirmView(discord.ui.View):
    """Confirmation view for wiping all ECODA records."""

    def __init__(self, author_id: int, on_confirm):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.on_confirm = on_confirm

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ This confirmation is not for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⚠️ Yes, Reset All ECODA Data", style=discord.ButtonStyle.danger, row=0)
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await self.on_confirm(interaction)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ ECODA reset cancelled. No data was deleted.", embed=None, view=None)


# ==========================================
# COG CLASS
# ==========================================
class EcodaCog(commands.Cog):
    """Cog providing ECODA daily work hours upload, edit, config, and activity leaderboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_upload
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_upload",
        description="Upload daily ECODA work hours sheet (.csv or .xlsx) [Team Leader / Admin only].",
    )
    @app_commands.describe(
        file="Excel (.xlsx) or CSV file with work_time, user_name, default_role",
        team="Team Name for this upload (e.g. Alpha, Team 1, Titans) [Optional]",
        date="Record date in YYYY-MM-DD format (defaults to today)",
    )
    async def ecoda_upload(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        team: str | None = None,
        date: str | None = None,
    ):
        # 1. Permission check
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can upload ECODA sheets.",
                ephemeral=True,
            )
            return

        # 2. Upload channel restriction check
        upload_channel_id = await get_setting("ecoda_upload_channel_id")
        if upload_channel_id and upload_channel_id.isdigit():
            target_ch_id = int(upload_channel_id)
            if interaction.channel_id != target_ch_id:
                await interaction.response.send_message(
                    f"❌ **Wrong Channel:** ECODA sheets can only be uploaded in <#{target_ch_id}>.",
                    ephemeral=True,
                )
                return

        # 3. File extension check
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("csv", "xlsx", "xls"):
            await interaction.response.send_message(
                "❌ Please upload a valid **.csv** or **.xlsx** Excel file.",
                ephemeral=True,
            )
            return

        # 4. Determine record date (defaults to today in LOCAL_TZ)
        now_local = datetime.now(LOCAL_TZ)
        if date:
            parsed = parse_custom_date(date)
            if not parsed:
                await interaction.response.send_message(
                    "❌ Invalid date format! Please use `YYYY-MM-DD` (e.g. `2026-10-02`).",
                    ephemeral=True,
                )
                return
            record_date = parsed
        else:
            record_date = now_local.strftime("%Y-%m-%d")

        await interaction.response.defer(ephemeral=False)

        # 5. Read and parse file content (with optional team name)
        try:
            file_bytes = await file.read()
            records = parse_ecoda_file(file_bytes, file.filename, default_team_name=team)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to parse file: `{e}`")
            return

        if not records:
            await interaction.followup.send("⚠️ No worker records found in the uploaded file.")
            return

        # 6. Ensure guild members are fully loaded in cache
        if interaction.guild and not interaction.guild.chunked:
            try:
                await interaction.guild.chunk()
            except Exception:
                pass

        # 7. Match records with Discord server members
        matched_records = []
        unmatched_names = []
        total_work_time = 0.0

        for r in records:
            total_work_time += r["work_time"]
            m = find_member_by_name(interaction.guild, r["ecoda_name"])
            if m:
                r["user_id"] = m.id
                matched_records.append(f"<@{m.id}>")
            else:
                r["user_id"] = None
                unmatched_names.append(r["ecoda_name"])

        # 8. Save records to Database
        saved_count = await save_ecoda_records(
            records=records,
            record_date=record_date,
            uploaded_by=interaction.user.id,
        )

        # 9. Trigger dynamic live leaderboard refresh
        await update_live_leaderboard_messages(self.bot)

        # 10. Build detailed report Embed
        embed = discord.Embed(
            title="📋 ECODA Work Hours Upload Report",
            description=f"✅ Successfully processed and recorded data for **`{record_date}`**.",
            color=discord.Color.green(),
        )
        embed.add_field(name="📅 Record Date", value=f"`{record_date}`", inline=True)
        embed.add_field(name="👥 Total Workers", value=f"`{saved_count}`", inline=True)
        embed.add_field(name="⏱️ Total Hours", value=f"`{format_hours(total_work_time)}`", inline=True)
        if team and team.strip():
            embed.add_field(name="🛡️ Team Name", value=f"`{team.strip()}`", inline=True)
        embed.add_field(name="🟢 Matched with Discord", value=f"`{len(matched_records)}` workers", inline=True)
        embed.add_field(name="🟡 Unmatched Names", value=f"`{len(unmatched_names)}` workers", inline=True)
        embed.add_field(name="👤 Uploaded By", value=f"<@{interaction.user.id}>", inline=True)

        if unmatched_names:
            preview_unmatched = ", ".join(f"`{name}`" for name in unmatched_names[:15])
            if len(unmatched_names) > 15:
                preview_unmatched += f" ...and {len(unmatched_names) - 15} more"

            embed.add_field(
                name=f"⚠️ Unmatched Workers ({len(unmatched_names)})",
                value=(
                    f"{preview_unmatched}\n"
                    f"ℹ️ *Eder nickname Discord server er sathe match koreni. Leaderboard e eder sheet er name dekhabe. "
                    f"Discord nickname sheet er name onujayi change korle auto-link hoye jabe.*"
                ),
                inline=False,
            )

        embed.set_footer(text=f"File: {file.filename} • Re-uploading on the same date will update existing records.")
        await interaction.followup.send(embed=embed)

    async def _team_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Shared autocomplete callback for registered ECODA team names."""
        teams = await get_all_teams()
        current_clean = current.strip().lower()
        matches = [t for t in teams if current_clean in t.lower()] if current_clean else teams
        return [app_commands.Choice(name=t, value=t) for t in matches[:25]]

    @ecoda_upload.autocomplete("team")
    async def ecoda_upload_team_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._team_autocomplete(interaction, current)

    # ------------------------------------------
    # HELPER EXECUTION METHODS
    # ------------------------------------------
    async def _execute_add(
        self,
        interaction: discord.Interaction,
        worker: str,
        hours: float,
        record_date: str,
        role_type: int,
        team: str | None,
    ):
        """Executes manual record creation and updates live boards."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        clean_worker = worker.strip()
        digits = re.findall(r"\d+", clean_worker)
        member = None
        if digits and len(digits[0]) >= 15 and interaction.guild:
            member = interaction.guild.get_member(int(digits[0]))
        if not member and interaction.guild:
            member = find_member_by_name(interaction.guild, clean_worker)

        if member:
            user_id = member.id
            ecoda_name = member.display_name if clean_worker.startswith("<@") or clean_worker.isdigit() else clean_worker
        else:
            user_id = None
            ecoda_name = clean_worker

        res = await add_ecoda_manual_record(
            worker_name=ecoda_name,
            hours=hours,
            record_date=record_date,
            role_type=role_type,
            team_name=team,
            user_id=user_id,
            added_by=interaction.user.id,
        )

        await update_live_leaderboard_messages(self.bot)

        display_str, _ = resolve_member_display(interaction.guild, res["ecoda_name"], res.get("user_id"))
        role_badge = "🏷️ Labeler" if role_type == 0 else "🔍 Checker"

        embed = discord.Embed(
            title="✅ ECODA Work Hours Added",
            description=f"Successfully logged manual work record for {display_str}.",
            color=discord.Color.green(),
        )
        embed.add_field(name="📅 Record Date", value=f"`{record_date}`", inline=True)
        embed.add_field(name="⏱️ Work Hours", value=f"`{format_hours(res['hours'])}` ({round(res['hours'], 2)}h)", inline=True)
        embed.add_field(name="🏷️ Role", value=f"`{role_badge}`", inline=True)
        if res.get("team_name"):
            embed.add_field(name="🛡️ Team", value=f"`{res['team_name']}`", inline=True)
        embed.add_field(name="👤 Added By", value=f"<@{interaction.user.id}>", inline=True)
        embed.set_footer(text="Live dynamic leaderboards have been automatically refreshed.")

        if interaction.response.is_done():
            await interaction.edit_original_response(content="", embed=embed, view=None)
        else:
            await interaction.followup.send(embed=embed)

    async def _execute_edit(
        self,
        interaction: discord.Interaction,
        worker: str,
        hours: float,
        record_date: str,
        team: str | None,
        note: str | None,
    ):
        """Executes record modification and updates live boards."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        updated = await update_ecoda_work_time(
            worker_query=worker,
            record_date=record_date,
            new_hours=max(0.0, float(hours)),
            updater_id=interaction.user.id,
            team_name=team,
        )

        if not updated:
            msg = f"❌ Could not find any ECODA record matching `{worker}` on `{record_date}`. Please verify the name or date."
            if interaction.response.is_done():
                await interaction.edit_original_response(content=msg, embed=None, view=None)
            else:
                await interaction.followup.send(msg)
            return

        await update_live_leaderboard_messages(self.bot)

        display_str, _ = resolve_member_display(
            interaction.guild, updated["ecoda_name"], updated.get("user_id")
        )
        old_str = format_hours(updated["old_hours"])
        new_str = format_hours(updated["new_hours"])

        embed = discord.Embed(
            title="✏️ ECODA Work Hours Corrected",
            description=f"Successfully updated work hours for {display_str}.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="📅 Date", value=f"`{record_date}`", inline=True)
        embed.add_field(name="⏪ Previous Hours", value=f"`{old_str}` ({round(updated['old_hours'], 2)}h)", inline=True)
        embed.add_field(name="⏩ New Hours", value=f"`{new_str}` ({round(updated['new_hours'], 2)}h)", inline=True)
        if updated.get("team_name"):
            embed.add_field(name="🛡️ Team", value=f"`{updated['team_name']}`", inline=True)
        embed.add_field(name="👤 Corrected By", value=f"<@{interaction.user.id}>", inline=True)
        if note:
            embed.add_field(name="📝 Reason / Note", value=note, inline=False)

        embed.set_footer(text="Live dynamic leaderboards have been automatically refreshed.")
        if interaction.response.is_done():
            await interaction.edit_original_response(content="", embed=embed, view=None)
        else:
            await interaction.followup.send(embed=embed)

    async def _execute_delete(
        self,
        interaction: discord.Interaction,
        workers_query: str,
        record_date: str | None,
    ):
        """Executes record deletion for single or multiple comma-separated workers and updates live boards."""
        if not interaction.response.is_done():
            await interaction.response.defer()

        worker_list = [w.strip() for w in workers_query.split(",") if w.strip()]
        if not worker_list:
            msg = "❌ No valid worker names provided."
            if interaction.response.is_done():
                await interaction.edit_original_response(content=msg, embed=None, view=None)
            else:
                await interaction.followup.send(msg)
            return

        results = []
        total_deleted = 0
        for w in worker_list:
            d_count, matched_name = await delete_ecoda_record(w, record_date)
            total_deleted += d_count
            results.append((matched_name, d_count))

        if total_deleted == 0 and len(worker_list) == 1:
            msg = f"⚠️ No records found for `{worker_list[0]}`" + (f" on `{record_date}`." if record_date and record_date != "all" else ".")
            if interaction.response.is_done():
                await interaction.edit_original_response(content=msg, embed=None, view=None)
            else:
                await interaction.followup.send(msg)
            return

        await update_live_leaderboard_messages(self.bot)

        date_scope = "All Historical Dates" if not record_date or record_date.lower() == "all" else f"`{record_date}`"
        embed = discord.Embed(
            title="🗑️ ECODA Record(s) Deleted",
            description=f"Processed **`{len(worker_list)}`** worker(s) from database.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="📅 Scope / Date", value=date_scope, inline=True)
        embed.add_field(name="🔢 Total Rows Deleted", value=f"`{total_deleted}` record(s)", inline=True)
        embed.add_field(name="👤 Deleted By", value=f"<@{interaction.user.id}>", inline=True)

        lines = [f"• **`{name}`**: `{cnt}` row(s) deleted" for name, cnt in results[:15]]
        if len(results) > 15:
            lines.append(f"...and {len(results) - 15} more")
        embed.add_field(name="👥 Processed Workers", value="\n".join(lines), inline=False)
        embed.set_footer(text="Live dynamic leaderboards have been automatically refreshed.")

        if interaction.response.is_done():
            await interaction.edit_original_response(content="", embed=embed, view=None)
        else:
            await interaction.followup.send(embed=embed)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_add
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_add",
        description="Manually add or log missed ECODA work hours for a worker [Team Leader / Admin only].",
    )
    @app_commands.describe(
        worker="Worker's Discord mention (@user) or exact sheet name (e.g. ARC_Shikto)",
        hours="Work hours (e.g. 3.5)",
        role="Worker's role (Labeler or Checker)",
        team="Optional Team Name (e.g. Alpha, Titans)",
        date="Record date in YYYY-MM-DD format (leave empty to pick from Calendar)",
    )
    @app_commands.choices(
        role=[
            app_commands.Choice(name="🏷️ Labeler", value=0),
            app_commands.Choice(name="🔍 Checker", value=1),
        ]
    )
    async def ecoda_add(
        self,
        interaction: discord.Interaction,
        worker: str,
        hours: float,
        role: int = 0,
        team: str | None = None,
        date: str | None = None,
    ):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can add ECODA work hours.",
                ephemeral=True,
            )
            return

        if date:
            parsed = parse_custom_date(date)
            if not parsed:
                await interaction.response.send_message(
                    "❌ Invalid date format! Please use `YYYY-MM-DD` (e.g. `2026-10-02`) or leave date empty to select from the Calendar.",
                    ephemeral=True,
                )
                return
            await interaction.response.defer()
            await self._execute_add(interaction, worker, hours, parsed, role, team)
        else:
            role_badge = "🏷️ Labeler" if role == 0 else "🔍 Checker"
            prompt_embed = discord.Embed(
                title="📅 Select Date for ECODA Record",
                description=(
                    f"**Worker:** `{worker}`\n"
                    f"**Hours:** `{format_hours(hours)}` ({round(hours, 2)}h)\n"
                    f"**Role:** `{role_badge}`\n"
                    f"{f'**Team:** `{team}`\n' if team else ''}\n"
                    "👇 *Please select the record date from the cutoffs below or click **Today** / **Yesterday**:*"
                ),
                color=discord.Color.teal(),
            )

            async def on_picked(i: discord.Interaction, picked_date: str):
                await self._execute_add(i, worker, hours, picked_date, role, team)

            view = CalendarDatePickerView(author_id=interaction.user.id, on_date_selected=on_picked)
            await interaction.response.send_message(embed=prompt_embed, view=view)

    @ecoda_add.autocomplete("team")
    async def ecoda_add_team_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._team_autocomplete(interaction, current)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_edit
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_edit",
        description="Edit or correct a worker's work hours or team for a specific date [Team Leader / Admin only].",
    )
    @app_commands.describe(
        worker="Worker's Discord mention (@user) or exact sheet name (e.g. ARC_Shikto Kumar Das)",
        hours="Corrected work hours (e.g. 2.5 or 0)",
        team="Update or set Team Name for this worker [Optional]",
        date="Record date in YYYY-MM-DD format (leave empty to pick from Calendar)",
        note="Optional reason or note for this edit",
    )
    async def ecoda_edit(
        self,
        interaction: discord.Interaction,
        worker: str,
        hours: float,
        team: str | None = None,
        date: str | None = None,
        note: str | None = None,
    ):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can edit ECODA work hours.",
                ephemeral=True,
            )
            return

        if date:
            parsed = parse_custom_date(date)
            if not parsed:
                await interaction.response.send_message(
                    "❌ Invalid date format! Please use `YYYY-MM-DD` (e.g. `2026-10-02`) or leave date empty to select from the Calendar.",
                    ephemeral=True,
                )
                return
            await interaction.response.defer()
            await self._execute_edit(interaction, worker, hours, parsed, team, note)
        else:
            prompt_embed = discord.Embed(
                title="📅 Select Date to Edit ECODA Work Hours",
                description=(
                    f"**Worker:** `{worker}`\n"
                    f"**New Hours:** `{format_hours(hours)}` ({round(hours, 2)}h)\n\n"
                    "👇 *Please select the date to correct from the cutoffs below or click **Today** / **Yesterday**:*"
                ),
                color=discord.Color.blue(),
            )

            async def on_picked(i: discord.Interaction, picked_date: str):
                await self._execute_edit(i, worker, hours, picked_date, team, note)

            view = CalendarDatePickerView(author_id=interaction.user.id, on_date_selected=on_picked)
            await interaction.response.send_message(embed=prompt_embed, view=view)

    @ecoda_edit.autocomplete("team")
    async def ecoda_edit_team_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._team_autocomplete(interaction, current)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_delete
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_delete",
        description="Delete worker record(s) from ECODA database (supports multiple comma-separated workers).",
    )
    @app_commands.describe(
        workers="Worker sheet name(s) or Discord mention(s), comma-separated (e.g. Rahul, Suman, @Alex)",
        date="Specific date (YYYY-MM-DD), 'all' for all records, or leave empty to choose interactively",
    )
    async def ecoda_delete(
        self,
        interaction: discord.Interaction,
        workers: str,
        date: str | None = None,
    ):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can delete ECODA records.",
                ephemeral=True,
            )
            return

        if date:
            if date.lower() == "all":
                await interaction.response.defer()
                await self._execute_delete(interaction, workers, "all")
            else:
                parsed = parse_custom_date(date)
                if not parsed:
                    await interaction.response.send_message(
                        "❌ Invalid date format! Please use `YYYY-MM-DD` (e.g. `2026-10-02`), `'all'`, or leave date empty to select interactively.",
                        ephemeral=True,
                    )
                    return
                await interaction.response.defer()
                await self._execute_delete(interaction, workers, parsed)
        else:
            worker_list = [w.strip() for w in workers.split(",") if w.strip()]
            preview_targets = ", ".join(f"`{w}`" for w in worker_list[:10])
            if len(worker_list) > 10:
                preview_targets += f" ...and {len(worker_list) - 10} more"

            prompt_embed = discord.Embed(
                title=f"🗑️ Delete ECODA Records ({len(worker_list)} Worker(s))",
                description=(
                    f"**Targets:** {preview_targets}\n\n"
                    "How would you like to delete their data?\n"
                    "• **Delete ALL Dates**: Removes all historical records for these workers.\n"
                    "• **Today / Yesterday**: Removes records for today or yesterday only.\n"
                    "• **Pick from Calendar**: Select any specific date from the calendar."
                ),
                color=discord.Color.red(),
            )

            async def handle_delete_choice(i: discord.Interaction, choice: str):
                if choice == "calendar":
                    cal_embed = discord.Embed(
                        title="📅 Select Date to Delete",
                        description=f"Select the exact date to delete records for **`{len(worker_list)}`** worker(s):",
                        color=discord.Color.red(),
                    )

                    async def on_cal_selected(ci: discord.Interaction, picked_date: str):
                        await self._execute_delete(ci, workers, picked_date)

                    cal_view = CalendarDatePickerView(author_id=interaction.user.id, on_date_selected=on_cal_selected)
                    await i.response.edit_message(embed=cal_embed, view=cal_view)
                else:
                    await self._execute_delete(i, workers, choice)

            view = EcodaDeletePromptView(author_id=interaction.user.id, on_action=handle_delete_choice)
            await interaction.response.send_message(embed=prompt_embed, view=view)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_delete_date
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_delete_date",
        description="Delete ALL worker records for an entire specific date (e.g. faulty sheet) [Admin only].",
    )
    @app_commands.describe(
        date="Date in YYYY-MM-DD format (leave empty to pick from Calendar)",
    )
    async def ecoda_delete_date(
        self,
        interaction: discord.Interaction,
        date: str | None = None,
    ):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can delete ECODA records.",
                ephemeral=True,
            )
            return

        async def do_wipe_date(i: discord.Interaction, target_date: str):
            if not i.response.is_done():
                await i.response.defer()

            deleted_count = await delete_ecoda_by_date(target_date)
            await update_live_leaderboard_messages(self.bot)

            embed = discord.Embed(
                title="🗑️ Date Records Wiped",
                description=f"Successfully wiped all ECODA records for **`{target_date}`**.",
                color=discord.Color.dark_red(),
            )
            embed.add_field(name="📅 Target Date", value=f"`{target_date}`", inline=True)
            embed.add_field(name="🔢 Rows Deleted", value=f"`{deleted_count}` workers", inline=True)
            embed.add_field(name="👤 Deleted By", value=f"<@{i.user.id}>", inline=True)
            embed.set_footer(text="Live dynamic leaderboards have been automatically refreshed.")

            if i.response.is_done():
                await i.edit_original_response(content="", embed=embed, view=None)
            else:
                await i.followup.send(embed=embed)

        if date:
            parsed = parse_custom_date(date)
            if not parsed:
                await interaction.response.send_message(
                    "❌ Invalid date format! Please use `YYYY-MM-DD` (e.g. `2026-10-02`) or leave empty to pick from the Calendar.",
                    ephemeral=True,
                )
                return
            await interaction.response.defer()
            await do_wipe_date(interaction, parsed)
        else:
            prompt_embed = discord.Embed(
                title="📅 Select Date to Wipe",
                description="⚠️ *Select the date for which all uploaded ECODA records will be deleted from the database:*",
                color=discord.Color.dark_red(),
            )
            view = CalendarDatePickerView(author_id=interaction.user.id, on_date_selected=do_wipe_date)
            await interaction.response.send_message(embed=prompt_embed, view=view)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_exclude
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_exclude",
        description="Manage external/unwanted labelers to hide them permanently (supports multiple comma-separated).",
    )
    @app_commands.describe(
        action="Add to blacklist, remove from blacklist, or view list",
        workers="Worker sheet name(s) or Discord mention(s), comma-separated (e.g. Rahul, Suman, @Alex)",
        delete_records="If True, also deletes their past records from the database [Default: False]",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="➕ Add to Blacklist (Hide from Leaderboard)", value="add"),
            app_commands.Choice(name="➖ Remove from Blacklist (Unhide)", value="remove"),
            app_commands.Choice(name="📋 List All Excluded Workers", value="list"),
        ]
    )
    async def ecoda_exclude(
        self,
        interaction: discord.Interaction,
        action: str,
        workers: str | None = None,
        delete_records: bool = False,
    ):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only Administrators or Team Leaders can manage the ECODA blacklist.",
                ephemeral=True,
            )
            return

        if action in ("add", "remove") and not workers:
            await interaction.response.send_message(
                "❌ Please specify worker name(s) or mention(s) to add or remove (comma-separated if multiple).",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        if action == "add":
            raw_workers = [w.strip() for w in workers.split(",") if w.strip()]
            total_deleted = 0
            processed_names = []

            for w in raw_workers:
                clean_name = w
                digits = re.findall(r"\d+", clean_name)
                if digits and len(digits[0]) >= 15 and interaction.guild:
                    m = interaction.guild.get_member(int(digits[0]))
                    if m:
                        clean_name = m.display_name

                await add_ecoda_excluded_worker(clean_name, interaction.user.id)
                if delete_records:
                    d_count, _ = await delete_ecoda_record(clean_name, "all")
                    total_deleted += d_count
                processed_names.append(clean_name)

            await update_live_leaderboard_messages(self.bot)

            embed = discord.Embed(
                title=f"🚫 {len(processed_names)} Worker(s) Blacklisted & Excluded",
                description=(
                    "The specified workers have been added to the ECODA exclusion list.\n\n"
                    "• They will **NO LONGER appear** on any live or historical leaderboards.\n"
                    "• Future sheet uploads containing their names will be automatically skipped.\n"
                    + (f"• **`{total_deleted}`** existing records deleted from database." if delete_records else "• Existing database records retained (hidden from view).")
                ),
                color=discord.Color.red(),
            )
            embed.add_field(name="👤 Blacklisted By", value=f"<@{interaction.user.id}>", inline=True)
            preview_names = ", ".join(f"`{n}`" for n in processed_names[:15])
            if len(processed_names) > 15:
                preview_names += f" ...and {len(processed_names) - 15} more"
            embed.add_field(name="👥 Excluded Workers", value=preview_names, inline=False)
            embed.set_footer(text="Live dynamic leaderboards have been automatically refreshed.")
            await interaction.followup.send(embed=embed)

        elif action == "remove":
            raw_workers = [w.strip() for w in workers.split(",") if w.strip()]
            removed_names = []
            not_found = []

            for w in raw_workers:
                clean_name = w
                digits = re.findall(r"\d+", clean_name)
                if digits and len(digits[0]) >= 15 and interaction.guild:
                    m = interaction.guild.get_member(int(digits[0]))
                    if m:
                        clean_name = m.display_name

                if await remove_ecoda_excluded_worker(clean_name):
                    removed_names.append(clean_name)
                else:
                    not_found.append(clean_name)

            await update_live_leaderboard_messages(self.bot)

            embed = discord.Embed(
                title="✅ Worker(s) Removed from Blacklist",
                color=discord.Color.green(),
            )
            if removed_names:
                embed.add_field(
                    name=f"🟢 Removed ({len(removed_names)})",
                    value=", ".join(f"`{n}`" for n in removed_names),
                    inline=False,
                )
            if not_found:
                embed.add_field(
                    name=f"⚠️ Not Found in Blacklist ({len(not_found)})",
                    value=", ".join(f"`{n}`" for n in not_found),
                    inline=False,
                )
            embed.set_footer(text="Live dynamic leaderboards have been automatically refreshed.")
            await interaction.followup.send(embed=embed)

        elif action == "list":
            excluded_list = await get_ecoda_excluded_workers()
            if not excluded_list:
                embed = discord.Embed(
                    title="📋 ECODA Excluded Workers (Blacklist)",
                    description="*No workers are currently blacklisted. All uploaded workers appear on the leaderboard.*",
                    color=discord.Color.blue(),
                )
            else:
                lines = []
                for idx, item in enumerate(excluded_list, 1):
                    added_by_str = f"<@{item['added_by']}>" if item.get("added_by") else "Admin"
                    lines.append(f"`#{idx}` **`{item['ecoda_name']}`** — Added by {added_by_str}")
                embed = discord.Embed(
                    title=f"📋 ECODA Excluded Workers ({len(excluded_list)} Total)",
                    description=(
                        "The following workers are excluded from all leaderboards and skipped during uploads:\n\n"
                        + "\n".join(lines)
                    ),
                    color=discord.Color.dark_red(),
                )
                embed.set_footer(text="Use /ecoda_exclude action:Remove to restore any worker.")
            await interaction.followup.send(embed=embed)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_reset
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_reset",
        description="Reset/wipe ALL ECODA work hours while keeping Discord Voice tracking safe [Admin/Leader only].",
    )
    async def ecoda_reset(self, interaction: discord.Interaction):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only Administrators or authorized Team Leaders/Checkers can reset ECODA data.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="⚠️ Confirm ECODA Data Reset",
            description=(
                "Are you sure you want to reset all **ECODA Workforce Data**?\n\n"
                "• **Will be deleted**: All uploaded daily work hours & manual entries (`ecoda_records`).\n"
                "• **100% PRESERVED**: Discord Voice Activity tracking, bot configurations, and blacklist.\n"
                "• **Leaderboard**: Live ECODA leaderboard will immediately reset to clean state.\n\n"
                "⚠️ *This action is irreversible. Click the button below to confirm.*"
            ),
            color=discord.Color.red(),
        )

        async def do_reset(i: discord.Interaction):
            if not i.response.is_done():
                await i.response.defer()

            deleted_count = await reset_ecoda_records()
            await update_live_leaderboard_messages(self.bot)

            success_embed = discord.Embed(
                title="🔄 ECODA Dashboard Reset Complete",
                description=(
                    f"✅ Successfully wiped all **`{deleted_count}`** ECODA work records from the database.\n\n"
                    f"• **Discord Voice Tracking:** 100% Intact & Untouched\n"
                    f"• **Live ECODA Dashboard:** Refreshed and ready for fresh uploads\n"
                    f"• **Reset By:** <@{i.user.id}>"
                ),
                color=discord.Color.green(),
            )
            success_embed.set_footer(text="You can now start uploading fresh sheets via /ecoda_upload.")

            if i.response.is_done():
                await i.edit_original_response(content="", embed=success_embed, view=None)
            else:
                await i.followup.send(embed=success_embed)

        view = EcodaResetConfirmView(author_id=interaction.user.id, on_confirm=do_reset)
        await interaction.response.send_message(embed=embed, view=view)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_set_role
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_set_role",
        description="Set the Team Leader / Checker role authorized to upload & manage ECODA data [Admin only].",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="The role assigned to Team Leaders / Checkers")
    async def ecoda_set_role(self, interaction: discord.Interaction, role: discord.Role):
        await set_setting("ecoda_leader_role_id", str(role.id))
        await interaction.response.send_message(
            f"✅ **ECODA Leader Role Updated:** <@&{role.id}> has been set as the authorized role for uploading and managing ECODA data.",
            ephemeral=True,
        )

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_set_channel
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_set_channel",
        description="Set the designated channel where Team Leaders must upload ECODA sheets [Admin only].",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel for ECODA uploads")
    async def ecoda_set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await set_setting("ecoda_upload_channel_id", str(channel.id))
        await interaction.response.send_message(
            f"✅ **ECODA Upload Channel Updated:** Team leaders must now use <#{channel.id}> to upload ECODA files. Upload reports and responses will be delivered there.",
            ephemeral=True,
        )

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_settings
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_settings",
        description="View current ECODA configuration (role, upload channel, live leaderboards).",
    )
    async def ecoda_settings(self, interaction: discord.Interaction):
        role_id = await get_setting("ecoda_leader_role_id")
        channel_id = await get_setting("ecoda_upload_channel_id")
        live_ch_id = await get_setting("live_leaderboard_channel_id")

        role_str = f"<@&{role_id}>" if role_id and role_id.isdigit() else "`Checker` (Default Role Name)"
        ch_str = f"<#{channel_id}>" if channel_id and channel_id.isdigit() else "*Any Channel (No restriction)*"
        live_str = f"<#{live_ch_id}>" if live_ch_id and live_ch_id.isdigit() else "*Not Configured (use /setup_live_leaderboard)*"

        embed = discord.Embed(
            title="⚙️ ECODA Configuration & Settings",
            color=discord.Color.dark_teal(),
        )
        embed.add_field(name="🛡️ Authorized Leader Role", value=role_str, inline=False)
        embed.add_field(name="📤 Designated Upload Channel", value=ch_str, inline=False)
        embed.add_field(name="📊 Live Dynamic Leaderboards Channel", value=live_str, inline=False)
        embed.set_footer(text="Use /ecoda_set_role, /ecoda_set_channel, or /setup_live_leaderboard to adjust.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_leaderboard
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_leaderboard",
        description="View the interactive ECODA Activity Leaderboard with filters and pagination.",
    )
    @app_commands.describe(
        timeframe="Time range for leaderboard",
        role_filter="Filter by Labeler or Checker (Ranked separately)",
        status="Filter by Active or Inactive workers",
    )
    @app_commands.choices(
        timeframe=[
            app_commands.Choice(name="⏳ Current Cutoff", value="current_cutoff"),
            app_commands.Choice(name="⏪ Previous Cutoff", value="previous_cutoff"),
            app_commands.Choice(name="☀️ Today", value="today"),
            app_commands.Choice(name="📅 This Week", value="this_week"),
            app_commands.Choice(name="🟢 This Month", value="this_month"),
            app_commands.Choice(name="🔵 All Time", value="all_time"),
        ],
        role_filter=[
            app_commands.Choice(name="🏷️ Labelers Only", value="0"),
            app_commands.Choice(name="🔍 Checkers Only", value="1"),
            app_commands.Choice(name="👥 All Roles", value="all"),
        ],
        status=[
            app_commands.Choice(name="🟢 Active Members (Work > 0h)", value="active"),
            app_commands.Choice(name="🔴 Inactive Members (0h)", value="inactive"),
        ],
    )
    async def ecoda_leaderboard(
        self,
        interaction: discord.Interaction,
        timeframe: str = "current_cutoff",
        role_filter: str = "0",
        status: str = "active",
    ):
        await interaction.response.defer()
        rf = None if role_filter == "all" else int(role_filter)
        view = EcodaLeaderboardView(timeframe=timeframe, role_filter=rf, status_filter=status, page=1)
        await render_ecoda_leaderboard(interaction, view)

    # ------------------------------------------
    # SLASH COMMAND GROUP: /ecoda_team [Admin Only]
    # ------------------------------------------
    ecoda_team = app_commands.Group(
        name="ecoda_team",
        description="Manage registered ECODA teams for upload dropdown and status tracking [Admin only].",
        default_permissions=discord.Permissions(administrator=True),
    )

    @ecoda_team.command(name="add", description="Add a new team to the registered roster [Admin only].")
    @app_commands.describe(name="Name of the team to add (e.g. Delta Force, Titans)")
    async def team_add(self, interaction: discord.Interaction, name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Access Denied:** Only **Server Administrators** can manage ECODA teams.",
                ephemeral=True,
            )
            return

        ok, msg = await add_team(name)
        color = discord.Color.green() if ok else discord.Color.red()
        embed = discord.Embed(title="🛡️ ECODA Team Management", description=msg, color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        if ok:
            await update_live_leaderboard_messages(self.bot)

    @ecoda_team.command(name="remove", description="Remove a team from the active roster [Admin only].")
    @app_commands.describe(name="Name of the team to remove")
    async def team_remove(self, interaction: discord.Interaction, name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Access Denied:** Only **Server Administrators** can manage ECODA teams.",
                ephemeral=True,
            )
            return

        ok, msg = await remove_team(name)
        color = discord.Color.green() if ok else discord.Color.red()
        embed = discord.Embed(title="🛡️ ECODA Team Management", description=msg, color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        if ok:
            await update_live_leaderboard_messages(self.bot)

    @team_remove.autocomplete("name")
    async def team_remove_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        return await self._team_autocomplete(interaction, current)

    @ecoda_team.command(name="list", description="List all registered teams with activity statistics [Admin only].")
    async def team_list(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Access Denied:** Only **Server Administrators** can view the team roster.",
                ephemeral=True,
            )
            return

        teams_data = await get_team_details_list()
        if not teams_data:
            await interaction.response.send_message(
                "ℹ️ No registered teams found in the database.",
                ephemeral=True,
            )
            return

        active_count = sum(1 for t in teams_data if t["is_active"])
        embed = discord.Embed(
            title="🛡️ Registered ECODA Teams Roster",
            description=(
                f"**Active Teams:** `{active_count}` • **Total Registered:** `{len(teams_data)}`\n"
                "These teams appear automatically in the `/ecoda_upload` dropdown.\n"
            ),
            color=discord.Color.blue(),
        )

        lines = []
        for idx, t in enumerate(teams_data, 1):
            status_icon = "🟢" if t["is_active"] else "⚪ *(Inactive)*"
            workers = t["worker_count"]
            last_date = f"`{t['last_record_date']}`" if t["last_record_date"] else "*No uploads yet*"
            lines.append(f"`#{idx:02d}` {status_icon} **{t['name']}** — {workers} workers • Last upload: {last_date}")

        chunk = "\n".join(lines)
        if len(chunk) > 3900:
            chunk = chunk[:3890] + "..."
        embed.description += "\n" + chunk
        embed.set_footer(text="Use /ecoda_team add or /ecoda_team remove to manage teams.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------------------------------------
    # SLASH COMMAND: /ecoda_team_status [Checker / Admin]
    # ------------------------------------------
    @app_commands.command(
        name="ecoda_team_status",
        description="View daily ECODA file upload status for all teams [Checker / Admin only].",
    )
    @app_commands.describe(
        date="Record date in YYYY-MM-DD format (defaults to today)",
    )
    async def ecoda_team_status(
        self,
        interaction: discord.Interaction,
        date: str | None = None,
    ):
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can view team upload status.",
                ephemeral=True,
            )
            return

        now_local = datetime.now(LOCAL_TZ)
        if date:
            parsed = parse_custom_date(date)
            if not parsed:
                await interaction.response.send_message(
                    "❌ Invalid date format! Please use `YYYY-MM-DD` (e.g. `2026-10-02`).",
                    ephemeral=True,
                )
                return
            target_date = parsed
        else:
            target_date = now_local.strftime("%Y-%m-%d")

        await interaction.response.defer(ephemeral=False)
        status_data = await fetch_team_upload_status(target_date)
        embed = build_team_upload_status_embed(interaction.guild, status_data, target_date)
        view = OnDemandTeamUploadStatusView(record_date=target_date)
        await interaction.followup.send(embed=embed, view=view)


# ==========================================
# SETUP HOOK
# ==========================================
async def setup(bot: commands.Bot):
    await bot.add_cog(EcodaCog(bot))
