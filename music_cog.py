import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import itertools
import logging
from typing import Optional, Union
from ytdl_source import YTDLSource

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
                async with asyncio.timeout(300):
                    if self.loop_mode == 1 and self.current:
                        source = await YTDLSource.from_url(self.current.webpage_url, loop=self.bot.loop, stream=True)
                    else:
                        source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.from_url(source, loop=self.bot.loop, stream=True)
                except Exception as e:
                    await self._channel.send(f"Error processing song: {e}")
                    continue

            source.volume = self.volume
            self.current = source
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

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except:
            pass
        try:
            del self.players[guild.id]
        except:
            pass

    def get_player(self, interaction):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            player = MusicPlayer(interaction)
            self.players[interaction.guild.id] = player
        return player

    @app_commands.command(name="play", description="Plays a song.")
    @app_commands.describe(search="Song name or URL", channel_name="Name or ID of voice channel (optional)")
    async def play_(self, interaction: discord.Interaction, search: str, channel_name: str = None):
        logger.info(f"Play command: {search}")
        try:
            await interaction.response.defer()
            
            target_channel = None
            
            # 1. If channel_name is provided, find it
            if channel_name:
                # Search by name or ID
                for ch in interaction.guild.channels:
                    if isinstance(ch, discord.VoiceChannel) and (ch.name == channel_name or str(ch.id) == channel_name):
                        target_channel = ch
                        break
                if not target_channel:
                    return await interaction.followup.send(f"Could not find voice channel: {channel_name}")
            
            # 2. If no channel provided, use user's current channel
            if not target_channel:
                if interaction.user.voice:
                    target_channel = interaction.user.voice.channel
            
            # 3. If STILL no channel, but the command was sent in a voice channel, use that
            if not target_channel and isinstance(interaction.channel, discord.VoiceChannel):
                target_channel = interaction.channel

            if not target_channel:
                return await interaction.followup.send("Please join a voice channel or provide a channel name!")

            # Connect if not connected
            vc = interaction.guild.voice_client
            if not vc:
                logger.info(f"Connecting to {target_channel.name}")
                vc = await target_channel.connect()
            elif vc.channel.id != target_channel.id:
                logger.info(f"Moving to {target_channel.name}")
                await vc.move_to(target_channel)

            player = self.get_player(interaction)
            await player.queue.put(search)
            await interaction.followup.send(f"Added **{search}** to the queue.")

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}")

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
        if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
            await interaction.response.send_message("Skipped.")
        else:
            await interaction.response.send_message("Nothing to skip.", ephemeral=True)

    @app_commands.command(name="stop")
    async def stop_(self, interaction: discord.Interaction):
        await self.cleanup(interaction.guild)
        await interaction.response.send_message("Stopped.")

    @app_commands.command(name="queue")
    async def queue_info(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.response.send_message("Queue is empty.")
        upcoming = list(itertools.islice(player.queue._queue, 0, 10))
        fmt = '\n'.join(f'**{i+1}.** {song}' for i, song in enumerate(upcoming))
        await interaction.response.send_message(embed=discord.Embed(title="Queue", description=fmt))

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

async def setup(bot):
    await bot.add_cog(Music(bot))
