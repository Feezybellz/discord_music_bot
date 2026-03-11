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
    # RECENT DESKTOP USER AGENT (2026)
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    'headers': {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Ch-Ua': '"Google Chrome";v="140", "Chromium";v="140", "Not:A-Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
}

# 1. THE CLIENT COMBO - Android is often more stable for servers
ytdl_format_options['extractor_args'] = {
    'youtube': {
        'player_client': ['android', 'web'], 
        'player_skip': ['webpage', 'configs'],
    }
}

# 2. SMART COOKIE DETECTION
cookie_paths = [
    BASE_DIR / "cookies.txt",
    BASE_DIR / "cookie.txt",
    Path("/var/projects/discord_music_bot/cookie.txt"),
    Path("/var/projects/discord_music_bot/cookies.txt")
]

found_cookie = None
for p in cookie_paths:
    if p.exists():
        found_cookie = str(p)
        break

if found_cookie:
    logger.info(f"SUCCESS: Using cookie file at {found_cookie}")
    ytdl_format_options['cookiefile'] = found_cookie
else:
    logger.warning("CRITICAL: No cookies found.")

# 3. Handle PO_TOKEN
PO_TOKEN = os.getenv('PO_TOKEN')
VISITOR_DATA = os.getenv('VISITOR_DATA')
if PO_TOKEN and VISITOR_DATA:
    logger.info("PO_TOKEN found, adding to extractor args.")
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
