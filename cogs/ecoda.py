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

from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    LOCAL_TZ,
    find_member_by_name,
    format_hours,
    get_date_range,
    get_setting,
    is_ecoda_checker,
    parse_custom_date,
    parse_ecoda_file,
    resolve_member_display,
    save_ecoda_records,
    set_setting,
    update_ecoda_work_time,
    update_live_leaderboard_messages,
    fetch_ecoda_leaderboard_data,
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
        date="Record date in YYYY-MM-DD format (defaults to today)",
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
        # 1. Permission check
        if not await is_ecoda_checker(interaction.user):
            await interaction.response.send_message(
                "❌ **Access Denied:** Only members with the **Checker / Team Leader** role or Server Administrators can edit ECODA work hours.",
                ephemeral=True,
            )
            return

        # 2. Determine record date
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

        await interaction.response.defer()

        # 3. Update record in database
        updated = await update_ecoda_work_time(
            worker_query=worker,
            record_date=record_date,
            new_hours=max(0.0, float(hours)),
            updater_id=interaction.user.id,
            team_name=team,
        )

        if not updated:
            await interaction.followup.send(
                f"❌ Could not find any ECODA record matching `{worker}` on `{record_date}`. Please verify the name or date."
            )
            return

        # 4. Trigger live leaderboard refresh
        await update_live_leaderboard_messages(self.bot)

        # 5. Build response embed
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

        embed.set_footer(text="Live leaderboards have been automatically refreshed.")
        await interaction.followup.send(embed=embed)

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


# ==========================================
# SETUP HOOK
# ==========================================
async def setup(bot: commands.Bot):
    await bot.add_cog(EcodaCog(bot))
