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

class MusicBotGroup(app_commands.Group):
    """Grouped commands under /musicbot"""
    def __init__(self, bot, players):
        super().__init__(name="musicbot", description="All music related commands")
        self.bot = bot
        self.players = players

    def get_player(self, interaction):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            # We use interaction as a pseudo-context
            class PseudoCtx:
                def __init__(self, interaction, bot, cog):
                    self.interaction = interaction
                    self.bot = bot
                    self.guild = interaction.guild
                    self.channel = interaction.channel
                    self.cog = cog
            
            # Find the cog instance
            cog = self.bot.get_cog("Music")
            player = MusicPlayer(PseudoCtx(interaction, self.bot, cog))
            self.players[interaction.guild.id] = player
        return player

    @app_commands.command(name="play", description="Plays a song.")
    @app_commands.describe(search="Song name or URL", channel="The voice channel to join")
    async def play_(self, interaction: discord.Interaction, search: str, channel: Optional[discord.VoiceChannel] = None):
        logger.info(f"Play command: {search}")
        try:
            await interaction.response.defer()
            
            target_channel = channel
            
            # If no channel provided, use user's current channel
            if not target_channel:
                if interaction.user.voice:
                    target_channel = interaction.user.voice.channel

            if not target_channel:
                return await interaction.followup.send("Please select a voice channel or join one yourself!")

            # Connect if not connected
            vc = interaction.guild.voice_client
            if not vc:
                vc = await target_channel.connect()
            elif vc.channel.id != target_channel.id:
                await vc.move_to(target_channel)

            player = self.get_player(interaction)
            await player.queue.put(search)
            await interaction.followup.send(f"Added **{search}** to the queue.")

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            await interaction.followup.send(f"An error occurred: {e}")

    @app_commands.command(name="status", description="Shows the bot's current status and permissions.")
    async def status_(self, interaction: discord.Interaction):
        perms = interaction.app_permissions
        status_embed = discord.Embed(title="Bot Status Report", color=discord.Color.green())
        status_embed.add_field(name="Current Guild", value=f"{interaction.guild.name} ({interaction.guild.id})")
        status_embed.add_field(name="Total Guilds Seen", value=f"{len(self.bot.guilds)}")
        
        perm_list = [
            ("Connect", perms.connect),
            ("Speak", perms.speak),
            ("Use Slash Commands", perms.use_application_commands),
            ("View Channels", perms.view_channel),
            ("Send Messages", perms.send_messages),
            ("Embed Links", perms.embed_links)
        ]
        
        perm_str = "\n".join([f"{'✅' if val else '❌'} {name}" for name, val in perm_list])
        status_embed.add_field(name="Permissions Check", value=perm_str, inline=False)
        
        vc = interaction.guild.voice_client
        vc_status = f"Connected to: {vc.channel.name}" if vc else "Not connected to voice."
        status_embed.add_field(name="Voice Status", value=vc_status, inline=False)
        await interaction.response.send_message(embed=status_embed)

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
        cog = self.bot.get_cog("Music")
        await cog.cleanup(interaction.guild)
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

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        # Register the group
        self.bot.tree.add_command(MusicBotGroup(bot, self.players))

    async def cleanup(self, guild):
        try:
            await guild.voice_client.disconnect()
        except:
            pass
        try:
            del self.players[guild.id]
        except:
            pass

async def setup(bot):
    await bot.add_cog(Music(bot))
