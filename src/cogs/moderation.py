"""Main-server moderation commands and audit logging."""

from __future__ import annotations

import logging
import os
import json

from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from src.ui import create_cahc_embed
from src.core.constants import CAHC_RED, CAHC_ORANGE, CAHC_GREEN, CAHC_YELLOW

if TYPE_CHECKING:
    from src.core.bot import DiscordBot

logger = logging.getLogger(__name__)

# Moderation configuration.
MODERATOR_ROLE_IDS: dict[int, int] = {int(role_id): int(level) for role_id, level in json.loads(os.getenv("MODERATOR_ROLE_IDS", "{}")).items()}
MODERATION_LOG_CHANNEL_ID = int(os.getenv("MODERATION_LOG_CHANNEL_ID", "0"))


class Moderation(commands.Cog):
    """Main-server moderation system."""

    def __init__(self, bot: DiscordBot) -> None:
        self.bot = bot

    moderation = app_commands.Group(name="moderation", description="Main-server moderation commands.")

    async def has_moderation_level(self, interaction: discord.Interaction, level_requirement: int) -> bool:
        """Check whether a member meets the required moderation level."""

        # Main-server restriction.
        if (interaction.guild is None or interaction.guild.id != self.bot.settings.guild_id):
            return False

        if not isinstance(interaction.user, discord.Member):
            return False

        # Find the highest moderation level held by the member.
        member_level = max((MODERATOR_ROLE_IDS.get(role.id, 0) for role in interaction.user.roles), default=0)

        # Check the required level.
        if member_level < level_requirement:
            await interaction.response.send_message(f"You do not have permission to use this command.\nRequired moderation level: `{level_requirement}`.\nYour moderation level: `{member_level}`", ephemeral=True)
            return False
        return True

    async def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Retrieve the configured moderation log channel."""

        if MODERATION_LOG_CHANNEL_ID == 0:
            logger.error("MODERATION_LOG_CHANNEL_ID is not configured.")
            return None

        channel = guild.get_channel(MODERATION_LOG_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MODERATION_LOG_CHANNEL_ID)
            except discord.HTTPException:
                logger.exception("Could not retrieve moderation log channel.")
                return None
        if not isinstance(channel, discord.TextChannel):
            logger.error("Moderation log destination is not a text channel.")
            return None

        return channel

    async def _log_action(self, interaction: discord.Interaction, action: str, member: discord.Member, reason: str, colour: discord.Colour, extra: str | None = None) -> bool:
        """Record a moderation action in the log channel."""

        if interaction.guild is None:
            return False
        channel = await self._get_log_channel(interaction.guild)
        if channel is None:
            return False

        embed, files = create_cahc_embed(
            title=f"Moderation | {action}",
            colour=colour,
        )
        embed.add_field(
            name="Member",
            value=f"{member.mention}\n`{member.id}`",
            inline=True,
        )
        embed.add_field(
            name="Moderator",
            value=(
                f"{interaction.user.mention}\n"
                f"`{interaction.user.id}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False,
        )
        if extra is not None:
            embed.add_field(
                name="Additional information",
                value=extra,
                inline=False,
            )

        try:
            await channel.send(embed=embed)
            return True
        except discord.HTTPException:
            logger.exception("Failed to log moderation action: %s", action)
            return False

    async def _validate_target(self, interaction: discord.Interaction,  member: discord.Member) -> str | None:
        """Validate that the target can be moderated."""

        guild = interaction.guild
        if guild is None:
            return "This command must be used inside the main server."
        if not isinstance(interaction.user, discord.Member):
            return "Unable to identify your server membership."

        moderator = interaction.user
        if member.id == moderator.id:
            return "You cannot moderate yourself."
        if self.bot.user is not None and member.id == self.bot.user.id:
            return "You cannot moderate the bot."
        if member.id == guild.owner_id:
            return "You cannot moderate the server owner."
        
        # The moderator must outrank their target.
        if (moderator.id != guild.owner_id and member.top_role >= moderator.top_role):
            return "You cannot moderate someone with an equal or higher role."

        # The bot must also outrank its target.
        bot_member = guild.me
        if bot_member is None or member.top_role >= bot_member.top_role:
            return "The bot cannot moderate this member due to role hierarchy."

        return None

    async def _notify_member(self, member: discord.Member, action: str, reason: str) -> bool:
        """Attempt to notify a member by direct message."""

        embed, files = create_cahc_embed(
            title=f"Moderation Notice | {action}",
            description=(f"You have received a moderation action in\n**{member.guild.name}**."),
            colour=discord.Colour(CAHC_RED),
        )
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False,
        )

        try:
            await member.send(embed=embed)
            return True
        except discord.HTTPException:
            return False

    @moderation.command(name="ban", description="Permanently ban a member.")
    @app_commands.describe(member="Member to ban.", reason="Reason for the ban.")
    @app_commands.checks.bot_has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        if not await self.has_moderation_level(interaction, 50):
            return
        error = await self._validate_target(interaction, member)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._notify_member(member, "Ban", reason)

        await member.ban(reason=(f"{reason} | Moderator: {interaction.user} ({interaction.user.id})"))
        logged = await self._log_action(interaction,"Member Banned", member, reason, discord.Colour(CAHC_RED))

        await interaction.followup.send(f"Successfully banned **{member}**." + ("" if logged else "\nWarning: The moderation log could not be posted."), ephemeral=True)

    @moderation.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="Member to kick.", reason="Reason for the kick.")
    @app_commands.checks.bot_has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        if not await self.has_moderation_level(interaction, 15):
            return
        error = await self._validate_target(interaction, member)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await self._notify_member(member, "Kick", reason)

        await member.kick(reason=(f"{reason} | Moderator: {interaction.user} ({interaction.user.id})"))
        logged = await self._log_action(interaction, "Member Kicked", member, reason, discord.Colour(CAHC_ORANGE))

        await interaction.followup.send(f"Successfully kicked **{member}**." + ("" if logged else "\nWarning: The moderation log could not be posted."), ephemeral=True)

    @moderation.command(name="timeout", description="Temporarily timeout a member.")
    @app_commands.describe(member="Member to timeout.", duration="Duration in minutes (1–40320).", reason="Reason for the timeout.",)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: app_commands.Range[int, 1, 40320], reason: str) -> None:
        if not await self.has_moderation_level(interaction, 10):
            return
        error = await self._validate_target(interaction, member)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await self._notify_member(member, "Timeout", f"{reason}\nDuration: {duration} minutes.",)

        until = discord.utils.utcnow() + timedelta(minutes=duration)
        await member.timeout(until, reason=(f"{reason} | Moderator: {interaction.user} ({interaction.user.id})"))
        logged = await self._log_action(interaction, "Member Timed Out", member, reason, discord.Colour(CAHC_ORANGE), extra=f"Duration: {duration} minutes.")

        await interaction.followup.send(f"Successfully timed out **{member}** for **{duration} minutes**." + ("" if logged else "\nWarning: The moderation log could not be posted."), ephemeral=True)

    @moderation.command(
        name="warn",
        description="Issue a formal warning to a member.",
    )
    @app_commands.describe(
        member="Member to warn.",
        reason="Reason for the warning.",
    )
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ) -> None:

        if not await self.has_moderation_level(interaction, 5):
            return

        error = await self._validate_target(interaction, member)

        if error:
            await interaction.response.send_message(
                error,
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        notified = await self._notify_member(
            member,
            "Warning",
            reason,
        )

        logged = await self._log_action(
            interaction,
            "Member Warned",
            member,
            reason,
            discord.Colour.yellow(),
            extra=(
                "Direct message delivered."
                if notified
                else "Direct message could not be delivered."
            ),
        )

        await interaction.followup.send(
            f"Successfully warned **{member}**."
            + (
                ""
                if notified
                else "\nThe member's direct messages were unavailable."
            )
            + (
                ""
                if logged
                else "\nWarning: The moderation log could not be posted."
            ),
            ephemeral=True,
        )


async def setup(bot: DiscordBot) -> None:
    await bot.add_cog(Moderation(bot))