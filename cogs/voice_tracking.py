"""
cogs/voice_tracking.py — Voice state event listener and background tasks.

Handles:
  - on_voice_state_update: track joins, leaves, mute/deafen state changes
  - Deafen-to-AFK mover logic
  - AFK auto-kick after 5 minutes
  - periodic_sync  (every 60s) — flushes sessions to DB
  - monthly_report_task (midnight on the 1st) — sends automatic CSV
  - afk_and_deafen_monitor (every 30s) — moves/kicks deafened/AFK users
"""

import time
from datetime import datetime, time as dt_time

import discord
from discord.ext import commands, tasks

from utils import (
    AFK_CHANNEL_ID,
    REPORT_CHANNEL_ID,
    LOCAL_TZ,
    active_sessions,
    last_connected_channels,
    deafen_timestamps,
    afk_moved_timestamps,
    determine_state,
    flush_user_session,
    sync_all_sessions,
    generate_and_send_csv,
)


class VoiceTracking(commands.Cog):
    """Cog responsible for real-time voice session tracking and background maintenance tasks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Start background loops when the cog loads
        self.periodic_sync.start()
        self.monthly_report_task.start()
        self.afk_and_deafen_monitor.start()

    def cog_unload(self):
        """Clean up background tasks when the cog is unloaded."""
        self.periodic_sync.cancel()
        self.monthly_report_task.cancel()
        self.afk_and_deafen_monitor.cancel()

    # ==========================================
    # BACKGROUND TASKS
    # ==========================================

    @tasks.loop(seconds=60)
    async def periodic_sync(self):
        """Flush all in-memory voice sessions to the database every 60 seconds."""
        await sync_all_sessions()

    @tasks.loop(time=dt_time(hour=0, minute=0, tzinfo=LOCAL_TZ))
    async def monthly_report_task(self):
        """On the 1st of each month at midnight, send an automated CSV report."""
        now_local = datetime.now(LOCAL_TZ)
        if now_local.day == 1:
            if REPORT_CHANNEL_ID:
                channel = self.bot.get_channel(REPORT_CHANNEL_ID)
                if channel:
                    await generate_and_send_csv(channel, "last_month")

    @tasks.loop(seconds=30)
    async def afk_and_deafen_monitor(self):
        """
        Every 30 seconds:
        - Move users who have been deafened for >= 5 min to the AFK channel (or disconnect).
        - Disconnect users who have been in the AFK channel for >= 5 min.
        """
        now = time.time()
        for guild in self.bot.guilds:
            for member in guild.members:
                if not member.voice:
                    continue

                # --- Deafen-to-AFK logic ---
                if member.id in deafen_timestamps:
                    already_in_afk = AFK_CHANNEL_ID and getattr(member.voice.channel, "id", None) == AFK_CHANNEL_ID
                    if not already_in_afk and now - deafen_timestamps[member.id] >= 300:
                        try:
                            afk_channel = guild.get_channel(AFK_CHANNEL_ID) if AFK_CHANNEL_ID else None
                            if afk_channel:
                                await member.move_to(afk_channel)
                            else:
                                await member.move_to(None)
                            deafen_timestamps.pop(member.id, None)
                        except discord.Forbidden:
                            pass

                # --- AFK auto-kick logic ---
                if member.id in afk_moved_timestamps:
                    if now - afk_moved_timestamps[member.id] >= 300:
                        try:
                            await member.move_to(None)
                            afk_moved_timestamps.pop(member.id, None)
                        except discord.Forbidden:
                            pass

    # ==========================================
    # VOICE STATE EVENT
    # ==========================================

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Track every voice state change (join, leave, mute, deafen, channel switch)."""
        if member.bot:
            return

        now = time.time()

        # Flush the current session segment before mutating state
        if member.id in active_sessions:
            await flush_user_session(member.id)

        # --- User is in / moved to a voice channel ---
        if after.channel:
            state = determine_state(after)

            if member.id in active_sessions:
                existing = active_sessions[member.id]
                # Track last channel on a channel switch
                if before.channel and before.channel.id != after.channel.id:
                    last_connected_channels[member.id] = before.channel.name
                    last_vc = before.channel.name
                else:
                    last_vc = existing.get("last_channel_name", "None")

                join_ts = existing.get("join_timestamp") or now
            else:
                last_vc = last_connected_channels.get(member.id, "None")
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

        # --- User left all voice channels ---
        else:
            if member.id in active_sessions:
                last_vc = active_sessions[member.id].get("channel_name") or "None"
                last_connected_channels[member.id] = last_vc
                del active_sessions[member.id]
            elif before.channel:
                last_connected_channels[member.id] = before.channel.name

        # --- Update deafen timestamp tracking ---
        if after.channel and (after.self_deaf or after.deaf):
            if member.id not in deafen_timestamps:
                deafen_timestamps[member.id] = now
        else:
            deafen_timestamps.pop(member.id, None)

        # --- Update AFK channel timestamp tracking ---
        if AFK_CHANNEL_ID:
            if after.channel and after.channel.id == AFK_CHANNEL_ID:
                if member.id not in afk_moved_timestamps:
                    afk_moved_timestamps[member.id] = now
            else:
                afk_moved_timestamps.pop(member.id, None)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceTracking(bot))
