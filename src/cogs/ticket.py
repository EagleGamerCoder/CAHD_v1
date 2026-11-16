"""Ticket system."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from src.ui.embeds import create_pbac_embed, create_tickets_panel

if TYPE_CHECKING:
    from src.core.bot import DiscordBot

class TicketView(discord.ui.View):
    def __init__(self, cog: "Ticket") -> None:
        super().__init__(timeout=None)
        self.cog = cog

    """
    @discord.ui.button(label="General Support", style=discord.ButtonStyle.success, custom_id="pbac:ticket:gen", row=0)
    async def gen_support(self,interaction: discord.Interaction, button: discord.ui.Button) -> None:
        pass

    @discord.ui.button(label="Discord Support & Reports", style=discord.ButtonStyle.success, custom_id="pbac:ticket:dis", row=0)
        async def dis_support(self,interaction: discord.Interaction, button: discord.ui.Button) -> None:
            pass

    @discord.ui.button(label="In-game Support & Reports", style=discord.ButtonStyle.success, custom_id="pbac:ticket:game", row=0)
        async def game_support(self,interaction: discord.Interaction, button: discord.ui.Button) -> None:
            pass

    @discord.ui.button(label="Bug Reports", style=discord.ButtonStyle.success, custom_id="pbac:ticket:bug", row=0)
        async def bug_report(self,interaction: discord.Interaction, button: discord.ui.Button) -> None:
            pass
    """
    

class Ticket(commands.Cog):
    """Ticket system."""

    def __init__(self, bot: DiscordBot) -> None:
        self.bot = bot

    ticket = app_commands.Group(name="ticket", description="British Army ticket system.")

    @ticket.command(name="panel-send", description="Sends the ticket panel.")
    @app_commands.describe(channel="Channel where the ticket panel should be posted.")
    async def panel_send(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used inside the main PBA Discord server.", ephemeral=True)
            return
        if interaction.guild.id != self.bot.settings.guild_id:
            await interaction.response.send_message("This command can only be used inside the main PBA Discord server.", ephemeral=True)
            return

        embed, files = create_tickets_panel()
        await channel.send(embed=embed, files=files, view=TicketView(self))
        await interaction.response.send_message(f"Ticket panel posted in {channel.mention}.", ephemeral=True)

async def setup(bot: DiscordBot) -> None:
    """Load this cog as a discord.py extension."""
    await bot.add_cog(Ticket(bot))