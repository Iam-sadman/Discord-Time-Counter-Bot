import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import matplotlib
matplotlib.use("Agg") # VPS এ ডিসপ্লে ছাড়াই গ্রাফ রেন্ডার করার জন্য
import matplotlib.pyplot as plt
import io
import csv
import time
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
import asyncio
import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# ==========================================
# CONFIGURATION - LOADED FROM .ENV
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("DISCORD_TOKEN") 
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN or DISCORD_TOKEN is missing in your .env file!")

DB_FILE = os.getenv("DB_FILE", "voice_stats.db")

def get_env_id(key):
    val = os.getenv(key)
    return int(val) if val and val.strip().isdigit() else None

STATS_CHANNEL_ID = get_env_id("STATS_CHANNEL_ID")
REPORT_CHANNEL_ID = get_env_id("REPORT_CHANNEL_ID")
AFK_CHANNEL_ID = get_env_id("AFK_CHANNEL_ID")

LOCAL_TZ = ZoneInfo("Asia/Dhaka")

# ==========================================
# IN-MEMORY TRACKING
# ==========================================
active_sessions = {}
deafen_timestamps = {}       # {user_id: timestamp_deafened}
afk_moved_timestamps = {}    # {user_id: timestamp_moved_to_afk}

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def format_duration(seconds: float) -> str:
    """Converts raw seconds into a readable string (e.g., 2h 15m 30s)"""
    if not seconds or seconds <= 0:
        return "0s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    
    parts = []
    if h > 0: parts.append(f"{h}h")
    if m > 0: parts.append(f"{m}m")
    if s > 0 or not parts: parts.append(f"{s}s")
    return " ".join(parts)

def get_date_range(time_filter: str) -> tuple[str, str]:
    now = datetime.now(LOCAL_TZ)
    today_str = now.strftime("%Y-%m-%d")

    if time_filter == "today":
        return today_str, today_str
    elif time_filter == "this_week":
        start_of_week = now - timedelta(days=now.weekday())
        return start_of_week.strftime("%Y-%m-%d"), today_str
    elif time_filter == "this_month":
        start_of_month = now.replace(day=1)
        return start_of_month.strftime("%Y-%m-%d"), today_str
    elif time_filter == "last_month":
        first_day_this_month = now.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        return first_day_last_month.strftime("%Y-%m-%d"), last_day_last_month.strftime("%Y-%m-%d")
    elif time_filter == "this_year":
        start_of_year = now.replace(month=1, day=1)
        return start_of_year.strftime("%Y-%m-%d"), today_str
    elif time_filter == "all_time":
        return "2000-01-01", "2099-12-31"
    
    return today_str, today_str

def parse_custom_date(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None

def determine_state(voice_state: discord.VoiceState) -> str:
    if voice_state.self_deaf or voice_state.deaf:
        return "deafened"
    elif voice_state.self_mute or voice_state.mute:
        return "muted"
    else:
        return "unmuted"

# ==========================================
# DATABASE OPERATIONS
# ==========================================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("PRAGMA table_info(voice_activity)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if columns and 'month_year' in columns and 'record_date' not in columns:
            print("🚀 Upgrading database schema for daily tracking...")
            await db.execute("ALTER TABLE voice_activity RENAME TO voice_activity_old")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_activity (
                    user_id INTEGER,
                    user_name TEXT,
                    channel_id INTEGER,
                    channel_name TEXT,
                    record_date TEXT,
                    unmuted_seconds REAL DEFAULT 0,
                    muted_seconds REAL DEFAULT 0,
                    deafened_seconds REAL DEFAULT 0,
                    PRIMARY KEY (user_id, channel_id, record_date)
                )
            """)
            await db.execute("""
                INSERT INTO voice_activity (user_id, user_name, channel_id, channel_name, record_date, unmuted_seconds, muted_seconds, deafened_seconds)
                SELECT user_id, user_name, channel_id, channel_name, month_year || '-01', unmuted_seconds, muted_seconds, deafened_seconds
                FROM voice_activity_old
            """)
            await db.execute("DROP TABLE voice_activity_old")
            print("✅ Database successfully upgraded!")
        else:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voice_activity (
                    user_id INTEGER,
                    user_name TEXT,
                    channel_id INTEGER,
                    channel_name TEXT,
                    record_date TEXT,
                    unmuted_seconds REAL DEFAULT 0,
                    muted_seconds REAL DEFAULT 0,
                    deafened_seconds REAL DEFAULT 0,
                    PRIMARY KEY (user_id, channel_id, record_date)
                )
            """)
            
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_date ON voice_activity(user_id, record_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_date ON voice_activity(record_date)")
        await db.commit()

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
    record_date = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            INSERT INTO voice_activity (user_id, user_name, channel_id, channel_name, record_date, unmuted_seconds, muted_seconds, deafened_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, channel_id, record_date) DO UPDATE SET
                user_name = excluded.user_name,
                channel_name = excluded.channel_name,
                unmuted_seconds = unmuted_seconds + excluded.unmuted_seconds,
                muted_seconds = muted_seconds + excluded.muted_seconds,
                deafened_seconds = deafened_seconds + excluded.deafened_seconds
            """,
            (user_id, session["name"], session["channel_id"], session["channel_name"], record_date, unmuted, muted, deafened),
        )
        await db.commit()

async def sync_all_sessions():
    now = time.time()
    updates = []
    record_date = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    for user_id, session in active_sessions.items():
        elapsed = now - session["last_update"]
        if elapsed <= 0:
            continue

        session["last_update"] = now
        state = session["state"]
        unmuted = elapsed if state == "unmuted" else 0
        muted = elapsed if state == "muted" else 0
        deafened = elapsed if state == "deafened" else 0

        updates.append((
            user_id, session["name"], session["channel_id"], session["channel_name"],
            record_date, unmuted, muted, deafened
        ))

    if updates:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.executemany(
                """
                INSERT INTO voice_activity (user_id, user_name, channel_id, channel_name, record_date, unmuted_seconds, muted_seconds, deafened_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, channel_id, record_date) DO UPDATE SET
                    user_name = excluded.user_name,
                    channel_name = excluded.channel_name,
                    unmuted_seconds = unmuted_seconds + excluded.unmuted_seconds,
                    muted_seconds = muted_seconds + excluded.muted_seconds,
                    deafened_seconds = deafened_seconds + excluded.deafened_seconds
                """,
                updates
            )
            await db.commit()

async def fetch_user_stats(user_id: int, start_date: str, end_date: str):
    query = """
        SELECT channel_name, SUM(unmuted_seconds), SUM(muted_seconds), SUM(deafened_seconds)
        FROM voice_activity
        WHERE user_id = ? AND record_date BETWEEN ? AND ?
        GROUP BY channel_name
    """
    params = [user_id, start_date, end_date]

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    unmuted = sum((r[1] or 0.0) for r in rows) if rows else 0.0
    muted = sum((r[2] or 0.0) for r in rows) if rows else 0.0
    deafened = sum((r[3] or 0.0) for r in rows) if rows else 0.0
    total = unmuted + muted + deafened

    top_vc = "None"
    max_vc_time = 0.0
    channel_breakdown = []
    
    for r in rows:
        vc_unmuted = r[1] or 0.0
        vc_muted = r[2] or 0.0
        vc_deafened = r[3] or 0.0
        vc_total = vc_unmuted + vc_muted + vc_deafened

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

async def fetch_leaderboard_data(start_date: str, end_date: str):
    query = """
        SELECT user_id, user_name,
               SUM(unmuted_seconds), SUM(muted_seconds), SUM(deafened_seconds),
               SUM(unmuted_seconds + muted_seconds + deafened_seconds) as total
        FROM voice_activity
        WHERE record_date BETWEEN ? AND ?
        GROUP BY user_id
        ORDER BY total DESC
        LIMIT 10
    """
    params = (start_date, end_date)

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(query, params) as cursor:
            users = await cursor.fetchall()

        leaderboard = []
        for u in users:
            user_id, user_name, unmuted, muted, deafened, total = u
            if total <= 0:
                continue

            ch_query = """
                SELECT channel_name, SUM(unmuted_seconds + muted_seconds + deafened_seconds) as ch_total
                FROM voice_activity
                WHERE user_id = ? AND record_date BETWEEN ? AND ?
                GROUP BY channel_name
                ORDER BY ch_total DESC
                LIMIT 1
            """
            ch_params = (user_id, start_date, end_date)

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

def generate_stats_chart_sync(stats, channel_breakdown):
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(12, 6))

    ax1 = fig.add_subplot(121)
    labels = ['Unmuted', 'Muted', 'Deafened']
    sizes = [stats['unmuted'], stats['muted'], stats['deafened']]
    colors = ['#2ecc71', '#f1c40f', '#e74c3c']

    if sum(sizes) == 0:
        ax1.text(0.5, 0.5, 'No Voice Data Available', ha='center', va='center', fontsize=12)
        ax1.axis('off')
    else:
        explode = (0.05, 0.05, 0.05) 
        ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90, textprops={'color': "white", 'weight': "bold"})
    ax1.set_title('Audio State Distribution', fontsize=14, pad=15)

    ax2 = fig.add_subplot(122)
    if not channel_breakdown:
        ax2.text(0.5, 0.5, 'No Channel Data', ha='center', va='center', fontsize=12)
        ax2.axis('off')
    else:
        top_channels = channel_breakdown[:5]
        c_labels = [c[0][:12] + '...' if len(c[0]) > 12 else c[0] for c in top_channels]
        c_times = [c[1] / 3600 for c in top_channels]

        bars = ax2.bar(c_labels, c_times, color='#3498db', edgecolor='white', linewidth=1)
        ax2.set_ylabel('Hours Spent', fontsize=12)
        ax2.set_title('Top Voice Channels', fontsize=14, pad=15)
        plt.xticks(rotation=30, ha='right')

        for bar in bars:
            yval = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.05, f'{yval:.1f}h', ha='center', va='bottom', fontsize=10)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf

async def generate_and_send_csv(target, timeframe_label: str = "last_month"):
    await sync_all_sessions()
    start_date, end_date = get_date_range(timeframe_label)
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            """
            SELECT user_name, user_id, channel_name, SUM(unmuted_seconds), SUM(muted_seconds), SUM(deafened_seconds)
            FROM voice_activity
            WHERE record_date BETWEEN ? AND ?
            GROUP BY user_id, channel_name
            ORDER BY user_name, channel_name
        """,
            (start_date, end_date),
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            msg = f"ℹ️ `{start_date}` থেকে `{end_date}` পর্যন্ত কোনো ভয়েস ডাটা নেই।"
            if isinstance(target, discord.Interaction):
                await target.followup.send(msg)
            elif target:
                await target.send(msg)
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
        file_name = f"Voice_Report_{start_date}_to_{end_date}.csv"
        discord_file = discord.File(fp=io.BytesIO(output.getvalue().encode("utf-8")), filename=file_name)
        content_msg = f"📊 **Detailed Voice Activity Report** ({start_date} to {end_date})"

        if isinstance(target, discord.Interaction):
            await target.followup.send(content=content_msg, file=discord_file)
        elif target:
            await target.send(content=content_msg, file=discord_file)

# ==========================================
# INTERACTIVE UI CLASSES (VIEWS)
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


class LeaderboardView(discord.ui.View):
    def __init__(self, start_date: str = None, end_date: str = None, is_custom: bool = False):
        super().__init__(timeout=300)
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
            discord.SelectOption(label="Today", value="today", description="Today's leaderboard", emoji="☀️"),
            discord.SelectOption(label="This Week", value="this_week", description="This week's leaderboard", emoji="📅"),
            discord.SelectOption(label="This Month", value="this_month", description="Current month leaderboard", emoji="🟢"),
            discord.SelectOption(label="Last Month", value="last_month", description="Previous month leaderboard", emoji="🟡"),
            discord.SelectOption(label="This Year", value="this_year", description="Current year leaderboard", emoji="📆"),
            discord.SelectOption(label="All Time", value="all_time", description="Cumulative leaderboard", emoji="🔵"),
        ],
    )
    async def select_timeframe(self, interaction: discord.Interaction, select: discord.ui.Select):
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
# RENDER LOGIC HELPERS (CLEAN UI & SPACING)
# ==========================================
async def render_dashboard(interaction: discord.Interaction, member: discord.Member, view: DashboardView):
    stats = await fetch_user_stats(member.id, view.start_date, view.end_date)
    chart_buf = await asyncio.to_thread(generate_stats_chart_sync, stats, stats["channel_breakdown"])

    filter_labels = {
        "today": "☀️ Today",
        "this_week": "📅 This Week",
        "this_month": "🟢 This Month",
        "last_month": "🟡 Last Month",
        "this_year": "📆 This Year",
        "all_time": "🔵 All Time",
        "custom": "🔧 Custom Range"
    }

    label = filter_labels.get(view.current_filter, "🔧 Custom Range")
    date_str = f"({view.start_date} to {view.end_date})" if view.start_date != view.end_date else f"({view.start_date})"

    # Live Session Data Extractions
    session = active_sessions.get(member.id)
    if session:
        current_vc = session["channel_name"]
        join_time_formatted = datetime.fromtimestamp(session["join_timestamp"], LOCAL_TZ).strftime("%I:%M %p")
    else:
        current_vc = "Not in Voice"
        join_time_formatted = "N/A"

    last_vc = session.get("last_channel_name", "None") if session else "None"
    if not session and member.id in active_sessions: # fallback check
        pass

    embed = discord.Embed(
        title=f"🎙️ Voice Dashboard — {member.display_name}",
        color=discord.Color.blue(),
    )
    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
    
    # --- Clean Row 1: Timeframe, Total Voice Time, Primary Channel ---
    embed.add_field(name="⏳ Timeframe", value=f"`{label}`\n`{date_str}`", inline=True)
    embed.add_field(name="⏱️ Total Voice Time", value=f"`{format_duration(stats['total'])}`", inline=True)
    embed.add_field(name="🔊 Primary Channel", value=f"`{stats['top_vc']}`", inline=True)

    # --- Clean Row 2: Current VC, Join Time, Last Connected VC (Proper Spacing) ---
    embed.add_field(name="🎧 Current VC", value=f"`{current_vc}`", inline=True)
    embed.add_field(name="⏰ Join Time", value=f"`{join_time_formatted}`", inline=True)
    embed.add_field(name="↩️ Last Connected VC", value=f"`{last_vc}`", inline=True)

    # --- Clean Row 3: Detailed Breakdown ---
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


async def render_leaderboard(interaction: discord.Interaction, view: LeaderboardView):
    lb_data = await fetch_leaderboard_data(view.start_date, view.end_date)

    filter_labels = {
        "today": "☀️ Today",
        "this_week": "📅 This Week",
        "this_month": "🟢 This Month",
        "last_month": "🟡 Last Month",
        "this_year": "📆 This Year",
        "all_time": "🔵 All Time",
        "custom": "🔧 Custom Range"
    }

    label = filter_labels.get(view.current_filter, "🔧 Custom Range")
    date_str = f"({view.start_date} to {view.end_date})" if view.start_date != view.end_date else f"({view.start_date})"

    embed = discord.Embed(
        title=f"🏆 Server Voice Leaderboard",
        description=f"**Timeframe:** `{label}`\n**Range:** `{date_str}`\n\n",
        color=discord.Color.gold(),
    )

    if not lb_data:
        embed.description += "ℹ️ *No voice activity recorded for this timeframe yet.*"
    else:
        medals = ["🥇", "🥈", "🥉"]
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
            embed.description += line

    embed.set_footer(text="Showing Top 10 Most Active Voice Members")

    if interaction.response.is_done():
        await interaction.edit_original_response(content="", embed=embed, view=view)
    else:
        await interaction.followup.send(embed=embed, view=view)

# ==========================================
# BOT CLIENT AND BACKGROUND TASKS
# ==========================================
class VoiceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.members = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()
        periodic_sync.start()
        monthly_report_task.start()
        afk_and_deafen_monitor.start()
        await self.tree.sync()
        print(f"✅ Logged in as {self.user} & Slash commands synced.")

bot = VoiceBot()

@tasks.loop(seconds=60)
async def periodic_sync():
    await sync_all_sessions()

@tasks.loop(time=dt_time(hour=0, minute=0, tzinfo=LOCAL_TZ))
async def monthly_report_task():
    now_local = datetime.now(LOCAL_TZ)
    if now_local.day == 1:
        if REPORT_CHANNEL_ID:
            channel = bot.get_channel(REPORT_CHANNEL_ID)
            if channel:
                await generate_and_send_csv(channel, "last_month")

@tasks.loop(seconds=30)
async def afk_and_deafen_monitor():
    now = time.time()
    for guild in bot.guilds:
        for member in guild.members:
            if not member.voice: 
                continue
            
            if member.id in deafen_timestamps:
                if AFK_CHANNEL_ID and getattr(member.voice.channel, 'id', None) == AFK_CHANNEL_ID:
                    pass
                elif now - deafen_timestamps[member.id] >= 300:
                    try:
                        afk_channel = guild.get_channel(AFK_CHANNEL_ID)
                        if afk_channel:
                            await member.move_to(afk_channel)
                        else:
                            await member.move_to(None)
                        deafen_timestamps.pop(member.id, None)
                    except discord.Forbidden: 
                        pass
                    
            if member.id in afk_moved_timestamps:
                if now - afk_moved_timestamps[member.id] >= 300:
                    try:
                        await member.move_to(None)
                        afk_moved_timestamps.pop(member.id, None)
                    except discord.Forbidden: 
                        pass

# ==========================================
# EVENTS (VOICE STATE UPDATE WITH LAST VC LOGIC)
# ==========================================
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return

    now = time.time()

    # Flush live session before making changes
    if member.id in active_sessions:
        await flush_user_session(member.id)

    previous_channel_name = None

    # Handle disconnect or channel switch
    if before.channel:
        previous_channel_name = before.channel.name

    # If user is still in a voice channel (either switched or joined)
    if after.channel:
        state = determine_state(after)
        
        # Check if they were already tracked in memory to preserve join time & last channel
        if member.id in active_sessions:
            existing = active_sessions[member.id]
            # If changing channels, old channel becomes last_channel_name
            if before.channel and before.channel.id != after.channel.id:
                last_vc = before.channel.name
            else:
                last_vc = existing.get("last_channel_name", "None")
            
            join_ts = existing["join_timestamp"]
        else:
            # Fresh join from outside voice
            last_vc = "None"
            join_ts = now

        active_sessions[member.id] = {
            "channel_id": after.channel.id,
            "channel_name": after.channel.name,
            "last_channel_name": last_vc,
            "join_timestamp": join_ts,
            "state": state,
            "last_update": now,
            "name": member.display_name,
        }
    else:
        # Left voice entirely -> preserve last connected channel name before clearing session
        if member.id in active_sessions:
            last_vc = active_sessions[member.id]["channel_name"]
            # We store a brief temp state or keep it so when they check stats while disconnected they can see last VC, 
            # but for active session we clear it. Let's keep a record for last disconnected VC if needed:
            active_sessions[member.id] = {
                "channel_id": None,
                "channel_name": None,
                "last_channel_name": last_vc,
                "join_timestamp": None,
                "state": "unmuted",
                "last_update": now,
                "name": member.display_name,
            }
            # Or fully pop if they are out of voice and you prefer:
            # active_sessions.pop(member.id, None)

        if member.id in active_sessions and not active_sessions[member.id]["channel_id"]:
            # If they are completely out, maybe keep last_channel_name in a separate dict if they want to view stats while offline? 
            # Let's keep active_sessions updated or let it clean up after 1 min.
            pass

    # Update Deafen tracking
    if after.channel and (after.self_deaf or after.deaf):
        if member.id not in deafen_timestamps:
            deafen_timestamps[member.id] = now
    else:
        deafen_timestamps.pop(member.id, None)

    # Update AFK Channel tracking
    if AFK_CHANNEL_ID:
        if after.channel and after.channel.id == AFK_CHANNEL_ID:
            if member.id not in afk_moved_timestamps:
                afk_moved_timestamps[member.id] = now
        else:
            afk_moved_timestamps.pop(member.id, None)

# ==========================================
# SLASH COMMANDS
# ==========================================
@bot.tree.command(name="stats", description="View interactive voice activity dashboard for yourself or another user.")
@app_commands.describe(
    user="Select a user to view their stats (leave blank for yourself)",
    start_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-01)",
    end_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-15)"
)
async def stats_command(interaction: discord.Interaction, user: discord.Member = None, start_date: str = None, end_date: str = None):
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
            await interaction.followup.send("❌ `start_date` is formatted incorrectly! (Example: 2026-09-01)", ephemeral=True)
            return
        if end_date and not parsed_end:
            await interaction.followup.send("❌ `end_date` is formatted incorrectly! (Example: 2026-09-15)", ephemeral=True)
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


@bot.tree.command(name="leaderboard", description="View the top 10 most active voice channel members.")
@app_commands.describe(
    start_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-01)",
    end_date="Custom Search - Format YYYY-MM-DD (e.g. 2026-09-15)"
)
async def leaderboard_command(interaction: discord.Interaction, start_date: str = None, end_date: str = None):
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
            await interaction.followup.send("❌ `start_date` is formatted incorrectly! (Example: 2026-09-01)", ephemeral=True)
            return
        if end_date and not parsed_end:
            await interaction.followup.send("❌ `end_date` is formatted incorrectly! (Example: 2026-09-15)", ephemeral=True)
            return
        
        final_start = parsed_start or parsed_end
        final_end = parsed_end or parsed_start
        
        if final_start > final_end:
            final_start, final_end = final_end, final_start
            
        is_custom = True
    else:
        final_start, final_end = get_date_range("this_month")

    view = LeaderboardView(start_date=final_start, end_date=final_end, is_custom=is_custom)
    await render_leaderboard(interaction, view)


@bot.tree.command(name="report", description="Manually generate the current month's voice report CSV.")
async def report_command(interaction: discord.Interaction):
    if STATS_CHANNEL_ID and interaction.channel_id != STATS_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{STATS_CHANNEL_ID}>",
            ephemeral=True,
        )
        return

    await interaction.response.defer()
    await generate_and_send_csv(interaction, "this_month")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Command Error: {error}")
    msg = f"❌ কমান্ডটি প্রসেস করতে একটি সমস্যা হয়েছে: `{error}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except:
        pass

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
