import asyncio
import discord
import yt_dlp
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Custom logger to capture OAuth2 code from yt-dlp
class OAuthLogger:
    def __init__(self, loop, interaction):
        self.loop = loop
        self.interaction = interaction
        self.code_found = False

    def debug(self, msg):
        if "google.com/device" in msg and not self.code_found:
            self.code_found = True
            # Send the found link/code to Discord
            asyncio.run_coroutine_threadsafe(self.interaction.followup.send(f"🔗 **YouTube Login Required!**\n\n{msg}"), self.loop)

    def warning(self, msg): pass
    def error(self, msg): pass

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'youtube_oauth': True
}

# Handle Proxy if present
PROXY = os.getenv('PROXY_URL')
if PROXY:
    ytdl_format_options['proxy'] = PROXY

# Handle PO_TOKEN
PO_TOKEN = os.getenv('PO_TOKEN')
VISITOR_DATA = os.getenv('VISITOR_DATA')
if PO_TOKEN and VISITOR_DATA:
    ytdl_format_options['extractor_args'] = {'youtube': {'po_token': [f"web+{PO_TOKEN}"]}}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.webpage_url = data.get('webpage_url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            raise e

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **{
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }), data=data)
