import asyncio
import discord
import yt_dlp
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('music_bot.ytdl')

# Get the directory where THIS file is located
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
    'source_address': '0.0.0.0', # Force IPv4
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    'youtube_include_dash_manifest': False,
    'youtube_include_hls_manifest': False,
}

# 1. DYNAMIC COOKIE DETECTION
# Priority: 1. .env path, 2. cookies.txt in folder, 3. cookie.txt in folder
env_cookie_path = os.getenv('COOKIE_PATH')
found_cookie = None

if env_cookie_path and Path(env_cookie_path).exists():
    found_cookie = env_cookie_path
else:
    # Fallback to searching the base directory
    for name in ["cookies.txt", "cookie.txt"]:
        p = BASE_DIR / name
        if p.exists():
            found_cookie = str(p)
            break

if found_cookie:
    logger.info(f"SUCCESS: Using cookie file at {found_cookie}")
    ytdl_format_options['cookiefile'] = found_cookie
else:
    logger.warning("CRITICAL: No cookies found. YouTube will likely block this server IP.")

# 2. Handle Proxy
PROXY = os.getenv('PROXY_URL')
if PROXY:
    ytdl_format_options['proxy'] = PROXY

# 3. Handle PO_TOKEN
PO_TOKEN = os.getenv('PO_TOKEN')
VISITOR_DATA = os.getenv('VISITOR_DATA')
if PO_TOKEN and VISITOR_DATA:
    ytdl_format_options['extractor_args'] = {
        'youtube': {
            'player_client': ['web', 'android'],
            'po_token': [f"web+{PO_TOKEN}"]
        }
    }
else:
    ytdl_format_options['extractor_args'] = {
        'youtube': {
            'player_client': ['web', 'android']
        }
    }

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
            # New instance per request to avoid session sticky blocks
            with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=not stream))
        except Exception as e:
            raise e

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **{
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }), data=data)
