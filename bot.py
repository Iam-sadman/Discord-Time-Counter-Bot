import asyncio
import calendar
import csv
import io
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", 0))
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


async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS voice_activity (
                user_id INTEGER,
                user_name TEXT,
                channel_id INTEGER,
                channel_name TEXT,
                unmuted_seconds REAL DEFAULT 0,
                muted_seconds REAL DEFAULT 0,
                deafened_seconds REAL DEFAULT 0,
                PRIMARY KEY (user_id, channel_id)
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

    state = session["state"]
    unmuted = elapsed if state == "unmuted" else 0
    muted = elapsed if state == "muted" else 0
    deafened = elapsed if state == "deafened" else 0

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            INSERT INTO voice_activity (user_id, user_name, channel_id, channel_name, unmuted_seconds, muted_seconds, deafened_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, channel_id) DO UPDATE SET
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
    return f"{h:02d}h {m:02d}m {s:02d}s"


async def generate_and_send_csv(channel: discord.TextChannel):
    for user_id in list(active_sessions.keys()):
        await flush_user_session(user_id)

    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("""
            SELECT user_name, user_id, channel_name, unmuted_seconds, muted_seconds, deafened_seconds
            FROM voice_activity
            ORDER BY user_name, channel_name
        """) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            await channel.send("ℹ️ No voice activity recorded for this period.")
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
        file_name = f"Voice_Report_{now_local.strftime('%Y-%m-%d')}.csv"
        discord_file = discord.File(fp=io.BytesIO(output.getvalue().encode("utf-8")), filename=file_name)

        await channel.send(
            content=f"📊 **Voice Activity Report** ({now_local.strftime('%Y-%m-%d %H:%M %Z')})",
            file=discord_file,
        )


# ----------------- EVENTS & ERROR HANDLER -----------------
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
        return

    new_state = determine_state(after)
    active_sessions[member.id] = {
        "channel_id": after.channel.id,
        "channel_name": after.channel.name,
        "state": new_state,
        "last_update": time.time(),
        "name": member.display_name,
    }


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
            await reset_database()
            await channel.send("🧹 **Monthly voice statistics have been automatically reset.**")
            await asyncio.sleep(60)


# ----------------- SLASH COMMANDS -----------------
@bot.tree.command(name="report", description="Generate current voice report CSV (Does NOT reset data).")
async def manual_report(interaction: discord.Interaction):
    await interaction.response.defer()
    await generate_and_send_csv(interaction.channel)
    await interaction.followup.send("📊 Report generated successfully! *(Data preserved)*", ephemeral=True)


@bot.tree.command(name="resetdata", description="Manually reset all recorded voice activity statistics.")
@app_commands.default_permissions(administrator=True)
async def reset_data_cmd(interaction: discord.Interaction):
    await reset_database()
    await interaction.response.send_message("🧹 **All voice activity statistics have been reset to zero.**", ephemeral=True)


bot.run(TOKEN)