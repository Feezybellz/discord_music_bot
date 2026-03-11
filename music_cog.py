import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import itertools
import logging
import os
from typing import Optional, Union
from ytdl_source import YTDLSource, ytdl, BASE_DIR

logger = logging.getLogger('music_bot.music')

class MusicPlayer:
    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'loop_mode')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.np = None
        self.volume = .5
        self.current = None
        self.loop_mode = 0
        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()
            try:
                if self.loop_mode == 1 and self.current:
                    source = await asyncio.wait_for(YTDLSource.from_url(self.current.webpage_url, loop=self.bot.loop, stream=True), timeout=300)
                else:
                    source = await asyncio.wait_for(self.queue.get(), timeout=300)
            except asyncio.TimeoutError:
                return self.destroy(self._guild)
            except Exception as e:
                logger.error(f"Error in loop: {e}")
                continue

            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.from_url(source, loop=self.bot.loop, stream=True)
                except Exception as e:
                    await self._channel.send(f"Error: {e}")
                    continue

            source.volume = self.volume
            self.current = source
            if self._guild.voice_client:
                self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
                embed = discord.Embed(title="Now Playing", description=f"[{source.title}]({source.webpage_url})", color=discord.Color.blue())
                self.np = await self._channel.send(embed=embed)
                await self.next.wait()
            
            source.cleanup()
            self.current = None
            if self.loop_mode == 2:
                await self.queue.put(source.webpage_url)

    def destroy(self, guild):
        return self.bot.loop.create_task(self._cog.cleanup(guild))

class MusicBotGroup(app_commands.Group):
    def __init__(self, bot, players):
        super().__init__(name="musicbot", description="All music related commands")
        self.bot = bot
        self.players = players

    def get_player(self, interaction):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            class PseudoCtx:
                def __init__(self, interaction, bot, cog):
                    self.interaction = interaction
                    self.bot = bot
                    self.guild = interaction.guild
                    self.channel = interaction.channel
                    self.cog = cog
            cog = self.bot.get_cog("Music")
            player = MusicPlayer(PseudoCtx(interaction, self.bot, cog))
            self.players[interaction.guild.id] = player
        return player

    @app_commands.command(name="check", description="Verify if the bot can see your cookie.txt file.")
    async def check_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            expected_paths = [
                os.path.join(BASE_DIR, "cookies.txt"),
                os.path.join(BASE_DIR, "cookie.txt")
            ]
            
            found = "❌ None"
            for p in expected_paths:
                if os.path.exists(p):
                    found = f"✅ Found at: {p}"
                    break
            
            # Internal yt-dlp config check
            ytdl_cookie = ytdl.params.get('cookiefile', '❌ Not loaded')
            ytdl_clients = ytdl.params.get('extractor_args', {}).get('youtube', {}).get('player_client', 'Default')
            
            # PO Token check
            po_token = os.getenv('PO_TOKEN')
            po_status = "✅ Present" if po_token else "❌ Missing (Highly recommended for servers)"

            status = (
                f"📂 **System Check**\n"
                f"Base Dir: `{BASE_DIR}`\n"
                f"File Status: {found}\n"
                f"PO Token: {po_status}\n\n"
                f"⚙️ **yt-dlp Internal Config**\n"
                f"Cookie Path: `{ytdl_cookie}`\n"
                f"Player Clients: `{ytdl_clients}`\n\n"
                f"*If any value looks wrong, restart the bot entirely.*"
            )
            await interaction.followup.send(status)
        except Exception as e:
            await interaction.followup.send(f"Error during check: {e}")

    @app_commands.command(name="play")
    @app_commands.describe(url="YouTube URL")
    async def play_(self, interaction: discord.Interaction, url: str, channel: Optional[discord.VoiceChannel] = None):
        try:
            await interaction.response.defer()
            player = self.get_player(interaction)
            while not player.queue.empty(): player.queue.get_nowait()
            target_channel = channel or (interaction.user.voice.channel if interaction.user.voice else None)
            if not target_channel: return await interaction.followup.send("Join a voice channel!")
            vc = interaction.guild.voice_client
            if not vc: vc = await target_channel.connect()
            elif vc.channel.id != target_channel.id: await vc.move_to(target_channel)
            if vc.is_playing() or vc.is_paused(): vc.stop()
            await player.queue.put(url)
            await interaction.followup.send(f"Playing **{url}**")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    queue_group = app_commands.Group(name="queue", description="Queue commands")
    @queue_group.command(name="add")
    async def queue_add(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        player = self.get_player(interaction)
        await player.queue.put(url)
        await interaction.followup.send("Added to queue.")

    @queue_group.command(name="list")
    async def queue_list(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.queue.empty(): return await interaction.response.send_message("Queue empty.")
        upcoming = list(itertools.islice(player.queue._queue, 0, 10))
        fmt = '\n'.join(f'**{i+1}.** {song}' for i, song in enumerate(upcoming))
        await interaction.response.send_message(embed=discord.Embed(title="Queue", description=fmt))

    @app_commands.command(name="stop")
    async def stop_(self, interaction: discord.Interaction):
        await self.bot.get_cog("Music").cleanup(interaction.guild)
        await interaction.response.send_message("Stopped.")

    @app_commands.command(name="skip")
    async def skip_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client: interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped.")

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.bot.tree.add_command(MusicBotGroup(bot, self.players))

    async def cleanup(self, guild):
        try: await guild.voice_client.disconnect()
        except: pass
        try: del self.players[guild.id]
        except: pass

async def setup(bot):
    await bot.add_cog(Music(bot))
