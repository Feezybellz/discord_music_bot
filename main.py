import asyncio
import os
import discord
import logging
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

# Configure Logging
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)
logger = logging.getLogger('music_bot')

class MusicBot(commands.Bot):
    def __init__(self):
        # We use all intents to be safe against caching issues
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        logger.info("Loading music_cog extension...")
        await self.load_extension('music_cog')
        logger.info("Syncing slash commands...")
        await self.tree.sync()
        logger.info(f"Synced slash commands for {self.user}")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info(f"Bot is currently in {len(self.guilds)} guilds:")
        for guild in self.guilds:
            logger.info(f" - {guild.name} (ID: {guild.id})")
        logger.info('------')

async def main():
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("DISCORD_TOKEN is not set correctly in the .env file.")
        return

    bot = MusicBot()
    async with bot:
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot is shutting down...")
    except Exception as e:
        logger.error(f"Fatal error during startup: {e}", exc_info=True)
