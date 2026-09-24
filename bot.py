import asyncio
import calendar
import csv
import io
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Set Matplotlib headless backend for Linux VPS compatibility
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", 0))
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID", 0))
AFK_CHANNEL_ID = int(os.getenv("AFK_CHANNEL_ID", 0))
TZ_NAME = os.getenv("TIMEZONE", "Asia/Dhaka")
LOCAL_TZ = ZoneInfo(TZ_NAME)

DB_FILE = "voice_tracker.db"

# ----------------- INTENTS & BOT SETUP -----------------
intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# In-memory tracking
active_sessions = {}
deafen_timestamps = {}       # {user_id: timestamp_deafened}
afk_moved_timestamps = {}    # {user_id: timestamp_moved_to_afk}


def get_current_month_str() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y-%m")


def get_last_month_str() -> str:
    now = datetime.now(LOCAL_TZ)
    first_day_this_month = now.replace(day=1)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    return last_day_last_month.strftime("%Y-%m")


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS voice_activity (
                user_id INTEGER,
                user_name TEXT,
                channel_id INTEGER,
                channel_name TEXT,
                month_year TEXT,
                unmuted_seconds REAL DEFAULT 0,
                muted_seconds REAL DEFAULT 0,
                deafened_seconds REAL DEFAULT 0,
                PRIMARY KEY (user_id, channel_id, month_year)
            )
        """)
        await db.commit()


def determine_state(voice_state: discord.VoiceState) -> str:
    if voice_state.self_deaf or voice_state.deaf:
        return "deafened"
    elif voice_state.self_mute or voice_state.mute:
        return "muted"
    else:
        return "unmuted"


async def flush_user_session(user_id: int):
    if user_id not in active_sessions:
        return

    session = active_sessions[user_id]
    now = time.time()
    elapsed = now - session["last_update"]
    session["last_update"] = now

    if elapsed <= 0:
        return

    state = session["state"]
    unmuted = elapsed if state == "unmuted" else 0
    muted = elapsed if state == "muted" else 0
    deafened = elapsed if state == "deafened" else 0
    month_year = get_current_month_str()

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            INSERT INTO voice_activity (user_id, user_name, channel_id, channel_name, month_year, unmuted_seconds, muted_seconds, deafened_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, channel_id, month_year) DO UPDATE SET
                user_name = excluded.user_name,
                channel_name = excluded.channel_name,
                unmuted_seconds = unmuted_seconds + excluded.unmuted_seconds,
                muted_seconds = muted_seconds + excluded.muted_seconds,
                deafened_seconds = deafened_seconds + excluded.deafened_seconds
            """,
            (
                user_id,
                session["name"],
                session["channel_id"],
                session["channel_name"],
                month_year,
                unmuted,
                muted,
                deafened,
            ),
        )
        await db.commit()


async def reset_database():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM voice_activity")
        await db.commit()


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"


# ----------------- CHART GENERATION -----------------
def generate_stats_chart_sync(stats: dict, channel_breakdown: list) -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5), gridspec_kw={'width_ratios': [1, 1.25]})
    fig.patch.set_facecolor("#2b2d31")  # Discord Dark Theme Background

    # 1. DONUT CHART
    ax1.set_facecolor("#2b2d31")
    unmuted = stats["unmuted"]
    muted = stats["muted"]
    deafened = stats["deafened"]
    total_sec = stats["total"]

    values = [unmuted, muted, deafened]
    labels = ["Unmuted", "Muted", "Deafened"]
    colors = ["#57F287", "#FEE75C", "#ED4245"]  # Green, Yellow, Red

    filtered = [(v, l, c) for v, l, c in zip(values, labels, colors) if v > 0]

    if not filtered or total_sec <= 0:
        ax1.pie([1], colors=["#4e5058"], wedgeprops=dict(width=0.35, edgecolor="#2b2d31", linewidth=2))
        ax1.text(0, 0, "No Activity", ha="center", va="center", color="#ffffff", fontsize=14, fontweight="bold")
    else:
        f_values = [d[0] for d in filtered]
        f_colors = [d[2] for d in filtered]

        ax1.pie(
            f_values,
            colors=f_colors,
            startangle=90,
            wedgeprops=dict(width=0.35, edgecolor="#2b2d31", linewidth=2),
        )

        hours = int(total_sec // 3600)
        mins = int((total_sec % 3600) // 60)
        secs = int(total_sec % 60)
        if hours > 0:
            center_text = f"{hours}h {mins}m\nTOTAL"
        elif mins > 0:
            center_text = f"{mins}m {secs}s\nTOTAL"
        else:
            center_text = f"{secs}s\nTOTAL"

        ax1.text(0, 0, center_text, ha="center", va="center", color="#ffffff", fontsize=13, fontweight="bold")

    ax1.set_title("State Breakdown", color="#ffffff", fontsize=12, fontweight="bold", pad=12)

    # 2. HORIZONTAL BAR CHART
    ax2.set_facecolor("#2b2d31")

    if not channel_breakdown or total_sec <= 0:
        ax2.text(0.5, 0.5, "No Channel Data", ha="center", va="center", color="#8e9297", fontsize=12, transform=ax2.transAxes)
        ax2.axis('off')
    else:
        top_channels = channel_breakdown[:5]
        top_channels.reverse()

        ch_names = [c[0] for c in top_channels]
        ch_times = [c[1] for c in top_channels]
        ch_names_clean = [name[:14] + "…" if len(name) > 14 else name for name in ch_names]

        bars = ax2.barh(ch_names_clean, ch_times, color="#5865F2", height=0.55, edgecolor="none")

        max_time = max(ch_times) if ch_times else 1
        for bar, time_sec in zip(bars, ch_times):
            width = bar.get_width()
            formatted = format_duration(time_sec)
            ax2.text(
                width + (max_time * 0.03),
                bar.get_y() + bar.get_height() / 2,
                formatted,
                ha='left',
                va='center',
                color='#ffffff',
                fontsize=9,
                fontweight='bold'
            )

        ax2.set_xlim(0, max_time * 1.38)
        ax2.tick_params(axis='y', colors='#dcddde', labelsize=10)
        ax2.tick_params(axis='x', colors='#8e9297', labelsize=8)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color('#4e5058')
        ax2.spines['bottom'].set_color('#4e5058')
        ax2.xaxis.grid(True, linestyle='--', alpha=0.3, color='#4e5058')
        ax2.set_axisbelow(True)

    ax2.set_title("Channel Breakdown", color="#ffffff", fontsize=12, fontweight="bold", pad=12)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), dpi=140)
    plt.close(fig)
    buf.seek(0)
    return buf


async def fetch_user_stats(user_id: int, time_filter: str):
    query = """
        SELECT channel_name, SUM(unmuted_seconds), SUM(muted_seconds), SUM(deafened_seconds)
        FROM voice_activity
        WHERE user_id = ?
    """
    params = [user_id]

    if time_filter == "this_month":
        query += " AND month_year = ?"
        params.append(get_current_month_str())
    elif time_filter == "last_month":
        query += " AND month_year = ?"
        params.append(get_last_month_str())

    query += " GROUP BY channel_name"

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    unmuted = sum(r[1] for r in rows) if rows else 0.0
    muted = sum(r[2] for r in rows) if rows else 0.0
    deafened = sum(r[3] for r in rows) if rows else 0.0
    total = unmuted + muted + deafened

    top_vc = "None"
    max_vc_time = 0.0
    channel_breakdown = []
    for r in rows:
        vc_total = r[1] + r[2] + r[3]
        if vc_total > 0:
            channel_breakdown.append((r[0], vc_total))
        if vc_total > max_vc_time:
            max_vc_time = vc_total
            top_vc = r[0]

    channel_breakdown.sort(key=lambda x: x[1], reverse=True)

    return {
        "unmuted": unmuted,
        "muted": muted,
        "deafened": deafened,
        "total": total,
        "top_vc": top_vc,
        "channel_breakdown": channel_breakdown,
    }


async def fetch_leaderboard_data(time_filter: str):
    month_str = None
    if time_filter == "this_month":
        month_str = get_current_month_str()
    elif time_filter == "last_month":
        month_str = get_last_month_str()

    if month_str:
        query = """
            SELECT user_id, user_name,
                   SUM(unmuted_seconds), SUM(muted_seconds), SUM(deafened_seconds),
                   SUM(unmuted_seconds + muted_seconds + deafened_seconds) as total
            FROM voice_activity
            WHERE month_year = ?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT 10
        """
        params = (month_str,)
    else:
        query = """
            SELECT user_id, user_name,
                   SUM(unmuted_seconds), SUM(muted_seconds), SUM(deafened_seconds),
                   SUM(unmuted_seconds + muted_seconds + deafened_seconds) as total
            FROM voice_activity
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT 10
        """
        params = ()

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(query, params) as cursor:
            users = await cursor.fetchall()

        leaderboard = []
        for u in users:
            user_id, user_name, unmuted, muted, deafened, total = u
            if total <= 0:
                continue

            if month_str:
                ch_query = """
                    SELECT channel_name, SUM(unmuted_seconds + muted_seconds + deafened_seconds) as ch_total
                    FROM voice_activity
                    WHERE user_id = ? AND month_year = ?
                    GROUP BY channel_name
                    ORDER BY ch_total DESC
                    LIMIT 1
                """
                ch_params = (user_id, month_str)
            else:
                ch_query = """
                    SELECT channel_name, SUM(unmuted_seconds + muted_seconds + deafened_seconds) as ch_total
                    FROM voice_activity
                    WHERE user_id = ?
                    GROUP BY channel_name
                    ORDER BY ch_total DESC
                    LIMIT 1
                """
                ch_params = (user_id,)

            async with db.execute(ch_query, ch_params) as ch_cursor:
                ch_row = await ch_cursor.fetchone()
                primary_ch = ch_row[0] if ch_row else "None"

            leaderboard.append({
                "user_id": user_id,
                "user_name": user_name,
                "unmuted": unmuted or 0.0,
                "muted": muted or 0.0,
                "deafened": deafened or 0.0,
                "total": total or 0.0,
                "primary_channel": primary_ch,
            })

    return leaderboard


async def generate_and_send_csv(channel: discord.TextChannel):
    for user_id in list(active_sessions.keys()):
        await flush_user_session(user_id)

    curr_month = get_current_month_str()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            """
            SELECT user_name, user_id, channel_name, unmuted_seconds, muted_seconds, deafened_seconds
            FROM voice_activity
            WHERE month_year = ?
            ORDER BY user_name, channel_name
        """,
            (curr_month,),
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await channel.send(f"ℹ️ No voice activity recorded for month `{curr_month}`.")
            return

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "User Name", "User ID", "Voice Channel",
            "Unmuted Time", "Muted Time", "Deafened Time", "Total Time",
            "Unmuted (Sec)", "Muted (Sec)", "Deafened (Sec)", "Total (Sec)"
        ])

        for row in rows:
            uname, uid, cname, unmuted, muted, deaf = row
            total = unmuted + muted + deaf
            writer.writerow([
                uname, uid, cname,
                format_duration(unmuted), format_duration(muted), format_duration(deaf), format_duration(total),
                round(unmuted, 2), round(muted, 2), round(deaf, 2), round(total, 2)
            ])

        output.seek(0)
        now_local = datetime.now(LOCAL_TZ)
        file_name = f"Voice_Report_{now_local.strftime('%Y-%m')}.csv"
        discord_file = discord.File(fp=io.BytesIO(output.getvalue().encode("utf-8")), filename=file_name)

        await channel.send(
            content=f"📊 **Monthly Voice Activity Report** ({now_local.strftime('%B %Y')})",
            file=discord_file,
        )


# ----------------- DASHBOARD VIEW & HELPERS -----------------
class DashboardView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=300)
        self.target_member = target_member
        self.current_filter = "this_month"

    @discord.ui.select(
        placeholder="Select Timeframe...",
        options=[
            discord.SelectOption(label="This Month", value="this_month", description="Current month voice stats", emoji="🟢", default=True),
            discord.SelectOption(label="Last Month", value="last_month", description="Previous month voice stats", emoji="🟡"),
            discord.SelectOption(label="All Time", value="all_time", description="Cumulative voice stats", emoji="🔵"),
        ],
    )
    async def select_timeframe(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_filter = select.values[0]
        for option in select.options:
            option.default = (option.value == self.current_filter)

        await interaction.response.defer()
        await render_dashboard(interaction, self.target_member, self.current_filter, self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await flush_user_session(self.target_member.id)
        await interaction.response.defer()
        await render_dashboard(interaction, self.target_member, self.current_filter, self)


async def render_dashboard(interaction: discord.Interaction, member: discord.Member, time_filter: str, view: DashboardView):
    stats = await fetch_user_stats(member.id, time_filter)

    chart_buf = await asyncio.to_thread(
        generate_stats_chart_sync,
        stats,
        stats["channel_breakdown"],
    )

    filter_labels = {
        "this_month": "🟢 This Month",
        "last_month": "🟡 Last Month",
        "all_time": "🔵 All Time",
    }

    embed = discord.Embed(
        title=f"🎙️ Voice Dashboard — {member.display_name}",
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="⏳ Timeframe", value=f"`{filter_labels[time_filter]}`", inline=True)
    embed.add_field(name="⏱️ Total Voice Time", value=f"`{format_duration(stats['total'])}`", inline=True)
    embed.add_field(name="🔊 Primary Channel", value=f"`{stats['top_vc']}`", inline=True)

    embed.add_field(
        name="📊 Breakdown",
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
        await interaction.response.send_message(embed=embed, file=file, view=view)


# ----------------- LEADERBOARD VIEW & HELPERS -----------------
class LeaderboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.current_filter = "this_month"

    @discord.ui.select(
        placeholder="Select Timeframe...",
        options=[
            discord.SelectOption(label="This Month", value="this_month", description="Current month leaderboard", emoji="🟢", default=True),
            discord.SelectOption(label="Last Month", value="last_month", description="Previous month leaderboard", emoji="🟡"),
            discord.SelectOption(label="All Time", value="all_time", description="Cumulative leaderboard", emoji="🔵"),
        ],
    )
    async def select_timeframe(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.current_filter = select.values[0]
        for option in select.options:
            option.default = (option.value == self.current_filter)

        await interaction.response.defer()
        await render_leaderboard(interaction, self.current_filter, self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for uid in list(active_sessions.keys()):
            await flush_user_session(uid)
        await interaction.response.defer()
        await render_leaderboard(interaction, self.current_filter, self)


async def render_leaderboard(interaction: discord.Interaction, time_filter: str, view: LeaderboardView):
    lb_data = await fetch_leaderboard_data(time_filter)

    filter_labels = {
        "this_month": "🟢 This Month",
        "last_month": "🟡 Last Month",
        "all_time": "🔵 All Time",
    }

    embed = discord.Embed(
        title=f"🏆 Voice Activity Leaderboard — {filter_labels[time_filter]}",
        color=discord.Color.gold(),
    )

    if not lb_data:
        embed.description = "ℹ️ No voice activity recorded for this timeframe."
    else:
        medals = ["🥇", "🥈", "🥉"]
        description_lines = []

        for idx, entry in enumerate(lb_data, start=1):
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
            description_lines.append(line)

        embed.description = "\n".join(description_lines)

    embed.set_footer(text="Top 10 Active Voice Members")

    if interaction.response.is_done():
        await interaction.edit_original_response(content="", embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)


# ----------------- EVENTS -----------------
@bot.event
async def on_ready():
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    print(f"Logged in as {bot.user.name} ({bot.user.id})")

    now = time.time()
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot or not member.voice:
                    continue
                state = determine_state(member.voice)
                active_sessions[member.id] = {
                    "channel_id": vc.id,
                    "channel_name": vc.name,
                    "state": state,
                    "last_update": now,
                    "name": member.display_name,
                }

    if not periodic_sync.is_running():
        periodic_sync.start()
    if not monthly_report_task.is_running():
        monthly_report_task.start()
    if not check_afk_deafened_users.is_running():
        check_afk_deafened_users.start()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ আপনার এই কমান্ডটি ব্যবহার করার মতো Administrator পারমিশন নেই।"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    else:
        print(f"Unhandled command error: {error}")


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if member.id in active_sessions:
        await flush_user_session(member.id)

    if after.channel is None:
        active_sessions.pop(member.id, None)
        deafen_timestamps.pop(member.id, None)
        afk_moved_timestamps.pop(member.id, None)
        return

    new_state = determine_state(after)
    active_sessions[member.id] = {
        "channel_id": after.channel.id,
        "channel_name": after.channel.name,
        "state": new_state,
        "last_update": time.time(),
        "name": member.display_name,
    }

    # Reset AFK tracking if user undeafens
    if new_state != "deafened":
        deafen_timestamps.pop(member.id, None)
        afk_moved_timestamps.pop(member.id, None)


# ----------------- BACKGROUND TASKS -----------------
@tasks.loop(seconds=60)
async def periodic_sync():
    for user_id in list(active_sessions.keys()):
        await flush_user_session(user_id)


@tasks.loop(minutes=1)
async def monthly_report_task():
    now = datetime.now(LOCAL_TZ)
    _, last_day = calendar.monthrange(now.year, now.month)

    if now.day == last_day and now.hour == 23 and now.minute == 59:
        channel = bot.get_channel(REPORT_CHANNEL_ID)
        if channel:
            await generate_and_send_csv(channel)
            await channel.send("📊 **Monthly CSV report generated. New tracking cycle started automatically!**")
            await asyncio.sleep(60)


@tasks.loop(seconds=15)
async def check_afk_deafened_users():
    if not AFK_CHANNEL_ID:
        return

    now = time.time()
    for guild in bot.guilds:
        afk_channel = guild.get_channel(AFK_CHANNEL_ID)
        if not afk_channel:
            continue

        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot or not member.voice:
                    continue

                is_deafened = member.voice.self_deaf or member.voice.deaf

                if is_deafened:
                    if vc.id != AFK_CHANNEL_ID:
                        # Step 1: Check 5 minutes in standard VC
                        if member.id not in deafen_timestamps:
                            deafen_timestamps[member.id] = now
                        elif (now - deafen_timestamps[member.id]) >= 300:  # 5 minutes
                            try:
                                await member.move_to(afk_channel, reason="Deafened in VC for 5+ minutes")
                                afk_moved_timestamps[member.id] = now
                                deafen_timestamps.pop(member.id, None)
                            except Exception as e:
                                print(f"Failed to move {member.display_name} to AFK channel: {e}")
                    else:
                        # Step 2: Check 5 minutes in AFK channel
                        if member.id not in afk_moved_timestamps:
                            afk_moved_timestamps[member.id] = now
                        elif (now - afk_moved_timestamps[member.id]) >= 300:  # 5 minutes in AFK
                            try:
                                await member.move_to(None, reason="Inactive in AFK channel for 5+ minutes")
                                afk_moved_timestamps.pop(member.id, None)
                                deafen_timestamps.pop(member.id, None)
                            except Exception as e:
                                print(f"Failed to disconnect {member.display_name}: {e}")
                else:
                    deafen_timestamps.pop(member.id, None)
                    afk_moved_timestamps.pop(member.id, None)


# ----------------- SLASH COMMANDS -----------------
@bot.tree.command(name="stats", description="View interactive voice activity dashboard for yourself or another user.")
@app_commands.describe(user="Select a user to view their stats (leave blank for yourself)")
async def stats_command(interaction: discord.Interaction, user: discord.Member = None):
    if STATS_CHANNEL_ID and interaction.channel_id != STATS_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ এই কমান্ডটি শুধুমাত্র <#{STATS_CHANNEL_ID}> চ্যানেলে ব্যবহার করা যাবে।",
            ephemeral=True,
        )
        return

    target_member = user or interaction.user
    if target_member.id in active_sessions:
        await flush_user_session(target_member.id)

    view = DashboardView(target_member)
    await render_dashboard(interaction, target_member, "this_month", view)


@bot.tree.command(name="leaderboard", description="View the top 10 most active voice channel members.")
async def leaderboard_command(interaction: discord.Interaction):
    if STATS_CHANNEL_ID and interaction.channel_id != STATS_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ এই কমান্ডটি শুধুমাত্র <#{STATS_CHANNEL_ID}> চ্যানেলে ব্যবহার করা যাবে।",
            ephemeral=True,
        )
        return

    for uid in list(active_sessions.keys()):
        await flush_user_session(uid)

    view = LeaderboardView()
    await render_leaderboard(interaction, "this_month", view)


@bot.tree.command(name="report", description="Generate current month voice report CSV.")
@app_commands.default_permissions(administrator=True)
async def manual_report(interaction: discord.Interaction):
    if REPORT_CHANNEL_ID and interaction.channel_id != REPORT_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ এই কমান্ডটি শুধুমাত্র প্রাইভেট এডমিন চ্যানেল <#{REPORT_CHANNEL_ID}> এ ব্যবহার করা যাবে।",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    await generate_and_send_csv(interaction.channel)
    await interaction.followup.send("📊 Report generated successfully!", ephemeral=True)


@bot.tree.command(name="resetdata", description="Manually reset all recorded voice activity statistics.")
@app_commands.default_permissions(administrator=True)
async def reset_data_cmd(interaction: discord.Interaction):
    if REPORT_CHANNEL_ID and interaction.channel_id != REPORT_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ এই কমান্ডটি শুধুমাত্র প্রাইভেট এডমিন চ্যানেল <#{REPORT_CHANNEL_ID}> এ ব্যবহার করা যাবে।",
            ephemeral=True,
        )
        return

    await reset_database()
    await interaction.response.send_message("🧹 **All voice activity statistics have been reset.**", ephemeral=True)


bot.run(TOKEN)
