import asyncio
import discord
import yt_dlp
import logging
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger('music_bot.ytdl')

BASE_DIR = Path(__file__).resolve().parent


def normalize_url(url: str) -> str:
    """Convert music.youtube.com URLs → www.youtube.com."""
    return re.sub(r'music\.youtube\.com', 'www.youtube.com', url)


def _find_cookie_file() -> str | None:
    candidates = []
    env_path = os.getenv('COOKIE_PATH')
    if env_path:
        candidates.append(Path(env_path))
    for name in ('cookies.txt', 'cookie.txt'):
        candidates.append(BASE_DIR / name)

    for p in candidates:
        logger.info(f"Cookie search: trying {p} ... {'FOUND' if p.exists() else 'not found'}")
        if p.exists():
            logger.info(f"Cookie file selected: {p}")
            return str(p)

    logger.warning(f"No cookie file found. Place cookie.txt in: {BASE_DIR}")
    return None


COOKIE_FILE = _find_cookie_file()
PROXY_URL = os.getenv('PROXY_URL')

if PROXY_URL:
    logger.info(f"Proxy loaded: {PROXY_URL.split('@')[-1]}")  # log host only, hide credentials
else:
    logger.warning(
        "No PROXY_URL set. On datacenter IPs (Azure/AWS/GCP), YouTube will block requests. "
        "Set PROXY_URL=http://user:pass@host:port in your .env file."
    )


def _build_ytdl_options() -> dict:
    opts = {
        'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best[acodec!=none]/best',
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
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
    }

    if COOKIE_FILE:
        opts['cookiefile'] = COOKIE_FILE

    # Route through residential proxy to bypass datacenter IP blocks
    if PROXY_URL:
        opts['proxy'] = PROXY_URL

    extractor_args: dict = {
        'youtube': {
            'player_client': ['music', 'ios', 'web', 'android', 'mweb'],
        }
    }

    po_token = os.getenv('PO_TOKEN')
    if po_token:
        token_val = po_token if po_token.startswith('web+') else f'web+{po_token}'
        extractor_args['youtube']['po_token'] = [token_val]
        logger.info('PO Token loaded.')

    opts['extractor_args'] = extractor_args
    return opts


ytdl_format_options = _build_ytdl_options()
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
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
    async def from_url(cls, url: str, *, loop=None, stream: bool = False):
        loop = loop or asyncio.get_event_loop()
        url = normalize_url(url)
        logger.debug(f"Extracting info for: {url}")

        try:
            with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
                data = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=not stream)
                )
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"yt-dlp DownloadError for {url}: {e}")
            raise RuntimeError(f"Could not retrieve audio: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error extracting {url}: {e}")
            raise

        if data is None:
            raise RuntimeError("yt-dlp returned no data. The video may be unavailable or geo-restricted.")

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)