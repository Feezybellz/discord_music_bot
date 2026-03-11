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
    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'loop_mode', 'current_url')

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
        self.current_url = None  # Crucial for looping
        self.loop_mode = 0  # 0: Off, 1: Track, 2: Queue
        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next.clear()
            
            # Decide what to play next
            url = None
            if self.loop_mode == 1 and self.current_url:
                # Mode 1: Track Loop - Use the same URL
                url = self.current_url
                logger.info(f"Looping Track: {url}")
            else:
                # Mode 0 or 2: Get next from queue
                try:
                    url = await asyncio.wait_for(self.queue.get(), timeout=300)
                    self.current_url = url # Save it for potential looping
                except asyncio.TimeoutError:
                    logger.info("Player idle timeout. Disconnecting.")
                    return self.destroy(self._guild)

            # Process the URL
            try:
                source = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            except Exception as e:
                logger.error(f"Extraction error in loop: {e}")
                await self._channel.send(f"Error processing song: {e}")
                self.current_url = None # Prevent looping a broken link
                continue

            source.volume = self.volume
            self.current = source
            
            if self._guild.voice_client:
                logger.info(f"Starting playback: {source.title}")
                self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
                
                embed = discord.Embed(title="Now Playing", description=f"[{source.title}]({source.webpage_url})", color=discord.Color.blue())
                if source.thumbnail:
                    embed.set_thumbnail(url=source.thumbnail)
                
                # Update Now Playing message
                if self.np:
                    try: await self.np.delete()
                    except: pass
                self.np = await self._channel.send(embed=embed)
                
                # Wait for song to finish
                await self.next.wait()
            
            # Post-playback cleanup
            source.cleanup()
            self.current = None
            
            # Mode 2: Queue Loop - Add the finished song back to the end
            if self.loop_mode == 2 and url:
                await self.queue.put(url)
            
            await asyncio.sleep(1) # Breath between tracks

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

    @app_commands.command(name="check")
    async def check_setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        found = "❌ None"
        for name in ["cookies.txt", "cookie.txt"]:
            if os.path.exists(os.path.join(BASE_DIR, name)):
                found = f"✅ Found {name}"
                break
        status = (f"📂 **Base Dir:** `{BASE_DIR}`\n"
                  f"🍪 **Cookie:** {found}\n"
                  f"🔑 **PO Token:** {'✅' if os.getenv('PO_TOKEN') else '❌'}")
        await interaction.followup.send(status)

    @app_commands.command(name="play")
    async def play_(self, interaction: discord.Interaction, url: str, channel: Optional[discord.VoiceChannel] = None):
        try:
            await interaction.response.defer()
            player = self.get_player(interaction)
            
            # Clear queue for instant play
            while not player.queue.empty(): player.queue.get_nowait()
            
            target_channel = channel or (interaction.user.voice.channel if interaction.user.voice else None)
            if not target_channel: return await interaction.followup.send("Join a voice channel!")
            
            vc = interaction.guild.voice_client
            if not vc: vc = await target_channel.connect()
            elif vc.channel.id != target_channel.id: await vc.move_to(target_channel)
            
            # Force current song to stop (triggers loop)
            if vc.is_playing() or vc.is_paused():
                vc.stop()

            await player.queue.put(url)
            await interaction.followup.send(f"Playing **{url}** immediately.")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

    queue_group = app_commands.Group(name="queue", description="Queue management")
    @queue_group.command(name="add")
    async def queue_add(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        player = self.get_player(interaction)
        await player.queue.put(url)
        await interaction.followup.send("Added to queue.")

    @queue_group.command(name="list")
    async def queue_list(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.queue.empty(): return await interaction.response.send_message("Queue is empty.")
        upcoming = list(itertools.islice(player.queue._queue, 0, 10))
        fmt = '\n'.join(f'**{i+1}.** {song}' for i, song in enumerate(upcoming))
        await interaction.response.send_message(embed=discord.Embed(title="Queue", description=fmt))

    @app_commands.command(name="pause")
    async def pause_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("Paused.")
        else: await interaction.response.send_message("Nothing playing.", ephemeral=True)

    @app_commands.command(name="resume")
    async def resume_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("Resumed.")
        else: await interaction.response.send_message("Not paused.", ephemeral=True)

    @app_commands.command(name="skip")
    async def skip_(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("Skipped.")

    @app_commands.command(name="stop")
    async def stop_(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("Music")
        await cog.cleanup(interaction.guild)
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
        await interaction.response.send_message(f"Loop mode set to **{mode.name}**.")

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
