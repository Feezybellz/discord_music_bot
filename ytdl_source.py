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
    return re.sub(r'music\.youtube\.com', 'www.youtube.com', url)


def _find_cookie_file() -> str | None:
    candidates = []
    env_path = os.getenv('COOKIE_PATH')
    if env_path:
        candidates.append(Path(env_path))
    for name in ('cookies.txt', 'cookie.txt'):
        candidates.append(BASE_DIR / name)

    for p in candidates:
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        logger.info(f"[COOKIE CHECK] {p} -> exists={exists}, size={size}b")
        if exists and size > 0:
            logger.info(f"[COOKIE] SELECTED: {p}")
            return str(p)
        elif exists and size == 0:
            logger.warning(f"[COOKIE] Found but EMPTY: {p} — skipping")

    logger.error(
        f"[COOKIE] No valid cookie file found!\n"
        f"  BASE_DIR={BASE_DIR}\n"
        f"  cwd={os.getcwd()}\n"
        f"  Files in BASE_DIR: {list(BASE_DIR.iterdir())}"
    )
    return None


COOKIE_FILE = _find_cookie_file()


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
        logger.info(f"[COOKIE] cookiefile set in yt-dlp opts: {COOKIE_FILE}")
    else:
        logger.error("[COOKIE] cookiefile NOT set — requests will likely be blocked by YouTube!")

    # Optional proxy support — set YTDL_PROXY=http://user:pass@host:port in .env
    proxy = os.getenv('YTDL_PROXY')
    if proxy:
        opts['proxy'] = proxy
        logger.info(f"[PROXY] Using proxy: {proxy}")

    extractor_args: dict = {
        'youtube': {
            'player_client': ['music', 'ios', 'web', 'android', 'mweb'],
        }
    }

    po_token = os.getenv('PO_TOKEN')
    if po_token:
        token_val = po_token if po_token.startswith('web+') else f'web+{po_token}'
        extractor_args['youtube']['po_token'] = [token_val]
        logger.info('[PO_TOKEN] Loaded.')

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
        logger.info(f"[YTDL] from_url called: {url} | cookie={COOKIE_FILE}")

        try:
            with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
                data = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=not stream)
                )
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"[YTDL] DownloadError: {e}")
            raise RuntimeError(f"Could not retrieve audio: {e}") from e
        except Exception as e:
            logger.error(f"[YTDL] Unexpected error: {e}")
            raise

        if data is None:
            raise RuntimeError("yt-dlp returned no data. Video may be unavailable or geo-restricted.")

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)