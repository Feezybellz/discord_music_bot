import asyncio
import discord
import yt_dlp
import logging
import os

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
    # Match a standard desktop browser to avoid "Reload" errors
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# Determine the best way to authenticate/bypass
cookie_file = None
if os.path.exists('cookies.txt'):
    cookie_file = 'cookies.txt'
elif os.path.exists('cookie.txt'):
    cookie_file = 'cookie.txt'

if cookie_file:
    logger.info(f"Found {cookie_file}, using it for authentication.")
    ytdl_format_options['cookiefile'] = cookie_file
else:
    logger.warning("No cookies.txt found. Using mobile spoofing bypass...")
    ytdl_format_options['youtube_include_dash_manifest'] = False
    ytdl_format_options['extractor_args'] = {
        'youtube': {
            'player_client': ['ios', 'mweb'],
            'player_skip': ['webpage', 'configs'],
        }
    }

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
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
        logger.info(f"Source prepared: {data.get('title')}")
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
