import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import itertools
import logging
from typing import Optional, Union
from ytdl_source import YTDLSource, ytdl

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
                # Python 3.10 compatible timeout
                if self.loop_mode == 1 and self.current:
                    source = await asyncio.wait_for(
                        YTDLSource.from_url(self.current.webpage_url, loop=self.bot.loop, stream=True),
                        timeout=300
                    )
                else:
                    source = await asyncio.wait_for(self.queue.get(), timeout=300)
            except asyncio.TimeoutError:
                logger.info(f"Player timeout in guild {self._guild.id}. Disconnecting.")
                return self.destroy(self._guild)
            except Exception as e:
                logger.error(f"Error getting next song: {e}", exc_info=True)
                continue

            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.from_url(source, loop=self.bot.loop, stream=True)
                except Exception as e:
                    await self._channel.send(f"Error processing song: {e}")
                    continue

            source.volume = self.volume
            self.current = source
            
            if self._guild.voice_client:
                self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
                
                embed = discord.Embed(title="Now Playing", description=f"[{source.title}]({source.webpage_url})", color=discord.Color.blue())
                embed.set_thumbnail(url=source.thumbnail)
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

    @app_commands.command(name="play", description="Plays a song immediately (Clears queue).")
    @app_commands.describe(url="YouTube URL", channel="Voice channel")
    async def play_(self, interaction: discord.Interaction, url: str, channel: Optional[discord.VoiceChannel] = None):
        try:
            await interaction.response.defer()
            player = self.get_player(interaction)
            
            while not player.queue.empty():
                player.queue.get_nowait()
            
            target_channel = channel or (interaction.user.voice.channel if interaction.user.voice else None)
            if not target_channel:
                return await interaction.followup.send("Join a voice channel first!")
            
            vc = interaction.guild.voice_client
            if not vc:
                vc = await target_channel.connect()
            elif vc.channel.id != target_channel.id:
                await vc.move_to(target_channel)
            
            if vc.is_playing() or vc.is_paused():
                vc.stop()

            await player.queue.put(url)
            await interaction.followup.send(f"Playing **{url}** immediately.")
        except Exception as e:
            logger.error(f"Error in play command: {e}", exc_info=True)
            await interaction.followup.send(f"Error: {e}")

    @app_commands.command(name="debug_play", description="Directly test YTDL and FFmpeg with a URL.")
    async def debug_play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        try:
            logger.info(f"DEBUG_PLAY: Attempting to extract {url}")
            source = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            
            vc = interaction.guild.voice_client
            if not vc:
                if interaction.user.voice:
                    vc = await interaction.user.voice.channel.connect()
                else:
                    return await interaction.followup.send("Join a voice channel first!")
            
            logger.info(f"DEBUG_PLAY: Playing {source.title}")
            vc.play(source)
            await interaction.followup.send(f"Now playing (DEBUG): {source.title}")
        except Exception as e:
            logger.error(f"DEBUG_PLAY ERROR: {e}", exc_info=True)
            await interaction.followup.send(f"DEBUG ERROR: {e}")

    queue_group = app_commands.Group(name="queue", description="Manage the music queue")

    @queue_group.command(name="add", description="Add a song or playlist to the end of the queue.")
    async def queue_add(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()
        player = self.get_player(interaction)
        
        if "list=" in url:
            data = await self.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False, process=False))
            if 'entries' in data:
                count = 0
                for entry in data['entries']:
                    if entry:
                        await player.queue.put(entry['url'])
                        count += 1
                return await interaction.followup.send(f"Added **{count}** songs to the queue.")
        
        await player.queue.put(url)
        await interaction.followup.send(f"Added to queue.")

    @queue_group.command(name="list", description="Show the current queue.")
    async def queue_list(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.response.send_message("Queue is empty.")
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
        cog = self.bot.get_cog("Music")
        await cog.cleanup(interaction.guild)
        await interaction.response.send_message("Stopped.")

    @app_commands.command(name="status")
    async def status_(self, interaction: discord.Interaction):
        perms = interaction.app_permissions
        status_embed = discord.Embed(title="Bot Status", color=discord.Color.green())
        status_embed.add_field(name="Guilds", value=f"{len(self.bot.guilds)}")
        perm_list = [("Connect", perms.connect), ("Speak", perms.speak)]
        perm_list_str = "\n".join([f"{'✅' if val else '❌'} {name}" for name, val in perm_list])
        status_embed.add_field(name="Voice Perms", value=perm_list_str)
        await interaction.response.send_message(embed=status_embed)

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
        music_group = MusicBotGroup(bot, self.players)
        self.bot.tree.add_command(music_group)

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except: pass
        try: del self.players[guild.id]
        except: pass

async def setup(bot):
    await bot.add_cog(Music(bot))
