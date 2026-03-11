import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import itertools
import logging
import os
from typing import Optional
from ytdl_source import YTDLSource, ytdl, BASE_DIR, COOKIE_FILE, ytdl_format_options

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

    @app_commands.command(name="check", description="Full diagnostic: cookie, proxy, PO token status.")
    async def check_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # Cookie file
            if COOKIE_FILE:
                from pathlib import Path
                p = Path(COOKIE_FILE)
                size = p.stat().st_size if p.exists() else 0
                cookie_status = f"✅ `{COOKIE_FILE}` ({size} bytes)"
            else:
                cookie_status = f"❌ Not found — place `cookie.txt` next to `ytdl_source.py`\n   Looking in: `{BASE_DIR}`"

            # Proxy
            proxy = os.getenv('YTDL_PROXY')
            proxy_status = f"✅ `{proxy}`" if proxy else "⚠️ Not set (may be needed on cloud VMs)"

            # PO Token
            po = os.getenv('PO_TOKEN')
            po_status = "✅ Present" if po else "⚠️ Not set"

            # yt-dlp internal confirm
            ytdl_cookie = ytdl_format_options.get('cookiefile', '❌ Not in opts')
            ytdl_clients = ytdl_format_options.get('extractor_args', {}).get('youtube', {}).get('player_client', 'Default')

            status = (
                f"📂 **File Paths**\n"
                f"Base Dir: `{BASE_DIR}`\n"
                f"Working Dir: `{os.getcwd()}`\n\n"
                f"🍪 **Cookie File**\n{cookie_status}\n\n"
                f"🌐 **Proxy** (for cloud/datacenter VMs)\n{proxy_status}\n\n"
                f"🔑 **PO Token**\n{po_status}\n\n"
                f"⚙️ **yt-dlp Internal Config**\n"
                f"cookiefile: `{ytdl_cookie}`\n"
                f"player_clients: `{ytdl_clients}`\n\n"
                f"*Restart the bot after any changes.*"
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

    @app_commands.command(name="pause")
    async def pause_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("Paused.")
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume")
    async def resume_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("Resumed.")
        else:
            await interaction.response.send_message("Music is not paused.", ephemeral=True)

    @app_commands.command(name="skip")
    async def skip_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("Skipped.")

    @app_commands.command(name="stop")
    async def stop_(self, interaction: discord.Interaction):
        await self.bot.get_cog("Music").cleanup(interaction.guild)
        await interaction.response.send_message("Stopped.")

    @app_commands.command(name="loop")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value=0),
        app_commands.Choice(name="Track", value=1),
        app_commands.Choice(name="Queue", value=2),
    ])
    async def loop_(self, interaction: discord.Interaction, mode: app_commands.Choice[int]):
        player = self.get_player(interaction)
        player.loop_mode = mode.value
        await interaction.response.send_message(f"Loop set to {mode.name}.")


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