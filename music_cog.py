import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import itertools
from ytdl_source import YTDLSource

class MusicPlayer:
    """A class which is assigned to each guild using the bot for Music.
    This class implements a queue and loop, which allows for different guilds to listen to different playlists
    simultaneously.
    """
    __slots__ = ('bot', '_guild', '_channel', '_cog', 'queue', 'next', 'current', 'np', 'volume', 'loop_mode')

    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self._cog = ctx.cog

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.np = None  # Now playing message
        self.volume = .5
        self.current = None
        self.loop_mode = 0  # 0: None, 1: Track, 2: Queue

        ctx.bot.loop.create_task(self.player_loop())

    async def player_loop(self):
        """Our main player loop."""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            self.next.clear()

            try:
                # Wait for the next song. If we timeout cancel the player and disconnect...
                async with asyncio.timeout(300):  # 5 minutes
                    if self.loop_mode == 1 and self.current:
                        # Re-use the current source for track loop
                        source = await YTDLSource.from_url(self.current.webpage_url, loop=self.bot.loop, stream=True)
                    else:
                        source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.destroy(self._guild)

            if not isinstance(source, YTDLSource):
                # Source was probably a stream (not downloaded)
                try:
                    source = await YTDLSource.from_url(source, loop=self.bot.loop, stream=True)
                except Exception as e:
                    await self._channel.send(f'There was an error processing your song.\n'
                                             f'```css\n[{e}]\n```')
                    continue

            source.volume = self.volume
            self.current = source

            self._guild.voice_client.play(source, after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set))
            
            embed = discord.Embed(title="Now Playing", description=f"[{source.title}]({source.webpage_url})", color=discord.Color.blue())
            embed.set_thumbnail(url=source.thumbnail)
            self.np = await self._channel.send(embed=embed)
            
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

            if self.loop_mode == 2:
                # Add the finished song back to the end of the queue for queue loop
                await self.queue.put(source.webpage_url)

    def destroy(self, guild):
        """Disconnect and cleanup the player."""
        return self.bot.loop.create_task(self._cog.cleanup(guild))


class Music(commands.Cog):
    """Music related commands."""
    __slots__ = ('bot', 'players')

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            del self.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx):
        """Retrieve the guild player, or create one."""
        try:
            player = self.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.players[ctx.guild.id] = player

        return player

    @app_commands.command(name="play", description="Plays a song from a URL or search term.")
    async def play_(self, interaction: discord.Interaction, search: str):
        """Request a song and add it to the queue."""
        await interaction.response.defer()
        
        vc = interaction.guild.voice_client

        if not vc:
            if interaction.user.voice:
                vc = await interaction.user.voice.channel.connect()
            else:
                return await interaction.followup.send("You are not connected to a voice channel.")

        player = self.get_player(interaction)

        # If download is False, source will be a dict which will be used to extract info later in the player loop.
        # For simplicity in this example, we just pass the search term to the player loop.
        await player.queue.put(search)
        await interaction.followup.send(f"Added **{search}** to the queue.")

    @app_commands.command(name="pause", description="Pauses the current song.")
    async def pause_(self, interaction: discord.Interaction):
        """Pause the currently playing song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_playing():
            return await interaction.response.send_message("I am not currently playing anything!", ephemeral=True)
        elif vc.is_paused():
            return await interaction.response.send_message("The music is already paused.", ephemeral=True)

        vc.pause()
        await interaction.response.send_message("Paused the music.")

    @app_commands.command(name="resume", description="Resumes the current song.")
    async def resume_(self, interaction: discord.Interaction):
        """Resume the currently paused song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I am not connected to a voice channel.", ephemeral=True)
        elif not vc.is_paused():
            return await interaction.response.send_message("The music is not paused.", ephemeral=True)

        vc.resume()
        await interaction.response.send_message("Resumed the music.")

    @app_commands.command(name="skip", description="Skips the current song.")
    async def skip_(self, interaction: discord.Interaction):
        """Skip the song."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_playing():
            return await interaction.response.send_message("I am not currently playing anything!", ephemeral=True)

        vc.stop()
        await interaction.response.send_message("Skipped the song.")

    @app_commands.command(name="stop", description="Stops the music and clears the queue.")
    async def stop_(self, interaction: discord.Interaction):
        """Stop the player and clear the queue."""
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.response.send_message("I am not connected to a voice channel.", ephemeral=True)

        await self.cleanup(interaction.guild)
        await interaction.response.send_message("Stopped the music and cleared the queue.")

    @app_commands.command(name="queue", description="Shows the current music queue.")
    async def queue_info(self, interaction: discord.Interaction):
        """Retrieve a basic list of upcoming songs."""
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.response.send_message("There are no more songs in the queue.", ephemeral=True)

        # Grab up to 10 songs from the queue
        upcoming = list(itertools.islice(player.queue._queue, 0, 10))

        fmt = '\n'.join(f'**{i+1}.** {song}' for i, song in enumerate(upcoming))
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt, color=discord.Color.blue())

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="loop", description="Sets the loop mode.")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value=0),
        app_commands.Choice(name="Track", value=1),
        app_commands.Choice(name="Queue", value=2),
    ])
    async def loop_(self, interaction: discord.Interaction, mode: app_commands.Choice[int]):
        """Set the loop mode."""
        player = self.get_player(interaction)
        player.loop_mode = mode.value
        await interaction.response.send_message(f"Loop mode set to **{mode.name}**.")

async def setup(bot):
    await bot.add_cog(Music(bot))
