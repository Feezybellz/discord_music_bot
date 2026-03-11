import asyncio
import discord
import yt_dlp
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('music_bot.ytdl')

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
    # Enable OAuth2 - This is the most stable method in 2026
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'mweb'],
            'player_skip': ['webpage', 'configs'],
        }
    }
}

# ENABLE OAUTH2
ytdl_format_options['youtube_oauth'] = True

# Handle Proxy if present
PROXY = os.getenv('PROXY_URL')
if PROXY:
    ytdl_format_options['proxy'] = PROXY

# Handle PO_TOKEN if present
PO_TOKEN = os.getenv('PO_TOKEN')
VISITOR_DATA = os.getenv('VISITOR_DATA')
if PO_TOKEN and VISITOR_DATA:
    ytdl_format_options['extractor_args']['youtube']['po_token'] = [f"web+{PO_TOKEN}"]

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
        logger.debug(f"Starting extraction for URL: {url}")
        
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            logger.error(f"YTDL extraction failed: {e}")
            raise

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **{
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }), data=data)
