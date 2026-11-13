"""Defines the creation of the Discord bot.

Loads cogs and syncs slash commands."""

from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from src.core import __version__

import discord
from discord.ext import commands

from src.core.config import Settings

class DiscordBot(commands.Bot):
    def __init__(self, ):