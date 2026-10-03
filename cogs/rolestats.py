"""
cogs/rolestats.py — /rolestats command with paginated RoleStatsView.

Provides:
  - /rolestats <role> [start_date] [end_date]
    Checks voice activity for all non-bot members of a role
    and generates an interactive embed + CSV export.
    Access is restricted to Administrators and configured allowed roles.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils import (
    format_duration,
    get_date_range,
    parse_custom_date,
    fetch_role_activity_data,
    generate_role_csv,
    can_use_rolestats,
    ROLESTATS_ALLOWED_ROLES,
)


# ==========================================
# ROLE STATS VIEW (interactive UI)
# ==========================================
class RoleStatsView(discord.ui.View):
    def __init__(self, data: dict, start_date: str, end_date: str, author_id: int):
        super().__init__(timeout=300)
        self.data = data
        self.start_date = start_date
        self.end_date = end_date
        self.author_id = author_id
        self.current_filter = "active" if self.data["active_users"] else "all"
        self.current_page = 0
        self.items_per_page = 10
        self.message = None

        # Row 0: Filter buttons
        self.btn_active = discord.ui.Button(emoji="🟢", row=0)
        self.btn_active.callback = self.on_active_click
        self.add_item(self.btn_active)

        self.btn_inactive = discord.ui.Button(emoji="⚪", row=0)
        self.btn_inactive.callback = self.on_inactive_click
        self.add_item(self.btn_inactive)

        self.btn_all = discord.ui.Button(emoji="👥", row=0)
        self.btn_all.callback = self.on_all_click
        self.add_item(self.btn_all)

        # Row 1: Pagination buttons
        self.btn_prev = discord.ui.Button(label="Prev", style=discord.ButtonStyle.primary, emoji="◀", row=1)
        self.btn_prev.callback = self.on_prev_click
        self.add_item(self.btn_prev)

        self.btn_page = discord.ui.Button(style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.add_item(self.btn_page)

        self.btn_next = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, emoji="▶", row=1)
        self.btn_next.callback = self.on_next_click
        self.add_item(self.btn_next)

        self.update_button_states()

    def get_filtered_list(self) -> list:
        if self.current_filter == "active":
            return self.data["active_users"]
        elif self.current_filter == "inactive":
            return self.data["inactive_users"]
        else:
            return self.data["all_users_sorted"]

    def get_total_pages(self) -> int:
        items = self.get_filtered_list()
        if not items:
            return 1
        return max(1, (len(items) + self.items_per_page - 1) // self.items_per_page)

    def update_button_states(self):
        total_pages = self.get_total_pages()
        self.current_page = max(0, min(self.current_page, total_pages - 1))

        # Filter button styles
        self.btn_active.style = discord.ButtonStyle.success if self.current_filter == "active" else discord.ButtonStyle.secondary
        self.btn_inactive.style = discord.ButtonStyle.danger if self.current_filter == "inactive" else discord.ButtonStyle.secondary
        self.btn_all.style = discord.ButtonStyle.primary if self.current_filter == "all" else discord.ButtonStyle.secondary

        self.btn_active.label = f"Active ({len(self.data['active_users'])})"
        self.btn_inactive.label = f"Inactive ({len(self.data['inactive_users'])})"
        self.btn_all.label = f"All ({self.data['total_members']})"

        # Pagination button states
        self.btn_prev.disabled = (self.current_page == 0)
        self.btn_next.disabled = (self.current_page >= total_pages - 1)
        self.btn_page.label = f"Page {self.current_page + 1}/{total_pages}"

    def build_embed(self) -> discord.Embed:
        role = self.data["role"]
        total_pages = self.get_total_pages()
        items = self.get_filtered_list()

        embed = discord.Embed(
            title=f"📊 Role Activity Report — @{role.name}",
            color=role.color if role.color.value != 0 else discord.Color.blue(),
        )

        divider = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        embed.description = (
            f"**Date Range:** `{self.start_date}` to `{self.end_date}`\n"
            f"{divider}"
        )

        # Overview fields
        embed.add_field(
            name="👥 Role Members",
            value=(
                f"• Total: `{self.data['total_members']}`\n"
                f"• Active: `{len(self.data['active_users'])}`\n"
                f"• Inactive: `{len(self.data['inactive_users'])}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="⏱️ Total Voice Time",
            value=f"**`{format_duration(self.data['total_time'])}`**",
            inline=True,
        )
        embed.add_field(
            name="🎧 Audio Breakdown",
            value=(
                f"🟢 **Unmuted:** `{format_duration(self.data['total_unmuted'])}`\n"
                f"🟡 **Muted:** `{format_duration(self.data['total_muted'])}`\n"
                f"🔴 **Deafened:** `{format_duration(self.data['total_deafened'])}`"
            ),
            inline=True,
        )

        embed.add_field(name="\u200b", value=divider, inline=False)

        filter_titles = {
            "active": "🟢 Active Members",
            "inactive": "⚪ Inactive Members",
            "all": "👥 All Role Members",
        }
        title_prefix = filter_titles.get(self.current_filter, "Members")

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = items[start_idx:end_idx]

        if not page_items:
            embed.add_field(
                name=f"{title_prefix} (0)",
                value="*No members found in this category for this period.*",
                inline=False,
            )
        else:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for idx_offset, u in enumerate(page_items):
                overall_idx = start_idx + idx_offset + 1
                u_name = u["name"]

                if u["total"] > 0:
                    rank_str = (
                        medals[overall_idx - 1]
                        if overall_idx <= 3 and self.current_filter != "inactive"
                        else f"`#{overall_idx}`"
                    )
                    tot = format_duration(u["total"])
                    unm = format_duration(u["unmuted"])
                    mut = format_duration(u["muted"])
                    deaf = format_duration(u["deafened"])
                    lines.append(
                        f"{rank_str} **{u_name}** — `{tot}`\n"
                        f"└ 🟢 `{unm}` | 🟡 `{mut}` | 🔴 `{deaf}`"
                    )
                else:
                    lines.append(f"`#{overall_idx}` **{u_name}** — `0s (Inactive)`")

            range_text = f"Showing {start_idx + 1}–{min(end_idx, len(items))} of {len(items)}"
            embed.add_field(
                name=f"{title_prefix} ({range_text})",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages} • Complete details in attached CSV")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        is_member = isinstance(interaction.user, discord.Member)
        is_authorized = is_member and can_use_rolestats(interaction.user)
        if interaction.user.id != self.author_id and not is_authorized:
            await interaction.response.send_message(
                "❌ You do not have permission to interact with this report.", ephemeral=True
            )
            return False
        return True

    async def on_active_click(self, interaction: discord.Interaction):
        self.current_filter = "active"
        self.current_page = 0
        self.update_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_inactive_click(self, interaction: discord.Interaction):
        self.current_filter = "inactive"
        self.current_page = 0
        self.update_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_all_click(self, interaction: discord.Interaction):
        self.current_filter = "all"
        self.current_page = 0
        self.update_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_prev_click(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_next_click(self, interaction: discord.Interaction):
        if self.current_page < self.get_total_pages() - 1:
            self.current_page += 1
        self.update_button_states()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


# ==========================================
# COG
# ==========================================
class RoleStatsCog(commands.Cog):
    """Cog providing the /rolestats slash command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="rolestats",
        description="Check voice activity and generate a CSV report for members of a specific role.",
    )
    @app_commands.describe(
        role="Select the role to check activity for (e.g. @labelers)",
        start_date="Start date - Format YYYY-MM-DD (e.g. 2026-09-01)",
        end_date="End date - Format YYYY-MM-DD (e.g. 2026-09-15)",
    )
    async def rolestats_command(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        start_date: str = None,
        end_date: str = None,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(interaction.user.id)
                except Exception:
                    pass

        if not member or not can_use_rolestats(member):
            user_roles = [f"{r.name}({r.id})" for r in getattr(member, "roles", [])]
            print(f"⚠️ Permission denied for {interaction.user} (User Roles: {user_roles}). Configured: {ROLESTATS_ALLOWED_ROLES}")
            await interaction.response.send_message(
                "❌ You do not have permission to use this command! (Requires Administrator or an authorized role).",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Validate dates
        if start_date or end_date:
            parsed_start = parse_custom_date(start_date) if start_date else None
            parsed_end = parse_custom_date(end_date) if end_date else None

            if start_date and not parsed_start:
                await interaction.followup.send("❌ Invalid `start_date`! Format must be YYYY-MM-DD (e.g. 2026-09-01).", ephemeral=True)
                return
            if end_date and not parsed_end:
                await interaction.followup.send("❌ Invalid `end_date`! Format must be YYYY-MM-DD (e.g. 2026-09-15).", ephemeral=True)
                return

            final_start = parsed_start or parsed_end
            final_end = parsed_end or parsed_start

            if final_start > final_end:
                final_start, final_end = final_end, final_start
        else:
            final_start, final_end = get_date_range("this_month")

        data = await fetch_role_activity_data(interaction.guild, role, final_start, final_end)
        if not data or data["total_members"] == 0:
            await interaction.followup.send(
                f"❌ No non-bot members found with the role {role.mention}.", ephemeral=True
            )
            return

        view = RoleStatsView(data, final_start, final_end, interaction.user.id)
        embed = view.build_embed()
        csv_file = generate_role_csv(data, final_start, final_end)
        msg = await interaction.followup.send(embed=embed, file=csv_file, view=view)
        view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleStatsCog(bot))
