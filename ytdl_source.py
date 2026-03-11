import asyncio
import discord
import yt_dlp
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('music_bot.ytdl')

BASE_DIR = Path(__file__).parent.resolve()

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
    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'youtube_include_dash_manifest': False,
}

# 1. DYNAMIC COOKIE DETECTION
env_cookie_path = os.getenv('COOKIE_PATH')
found_cookie = None
if env_cookie_path and Path(env_cookie_path).exists():
    found_cookie = env_cookie_path
else:
    for name in ["cookies.txt", "cookie.txt"]:
        if (BASE_DIR / name).exists():
            found_cookie = str(BASE_DIR / name)
            break

if found_cookie:
    logger.info(f"SUCCESS: Using cookie file at {found_cookie}")
    ytdl_format_options['cookiefile'] = found_cookie

# 2. CLIENT PRIORITY - ios/mweb are currently best for server IPs
ytdl_format_options['extractor_args'] = {
    'youtube': {
        'player_client': ['ios', 'mweb', 'android', 'web'],
        'player_skip': ['webpage', 'configs'],
    }
}

# 3. PO TOKEN
PO_TOKEN = os.getenv('PO_TOKEN')
if PO_TOKEN:
    # Ensure it uses the correct prefix
    token_val = f"web+{PO_TOKEN}" if not PO_TOKEN.startswith("web+") else PO_TOKEN
    ytdl_format_options['extractor_args']['youtube']['po_token'] = [token_val]

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
            # Always use a fresh instance to avoid session stickiness
            with yt_dlp.YoutubeDL(ytdl_format_options) as ydl_fresh:
                data = await loop.run_in_executor(None, lambda: ydl_fresh.extract_info(url, download=not stream))
        except Exception as e:
            raise e

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **{
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }), data=data)
