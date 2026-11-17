"""Download one YouTube video as MP4 or extract its audio as MP3."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class MediaDownloadResult:
    path: str
    title: str
    extension: str
    size: int


def youtube_thumbnail_url(url: str) -> Optional[str]:
    """Return a reliable YouTube thumbnail URL for supported single-video URLs."""
    value = url.strip()
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    video_id = None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
            video_id = parts[1]
    if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return None
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def _clean_error(error: Exception) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", str(error)).strip()


def _common_options() -> dict:
    options = {"noplaylist": True, "quiet": True, "no_warnings": True}
    cookie_file = os.getenv("YTDLP_COOKIE_FILE", "").strip()
    browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
    if cookie_file:
        if not os.path.isfile(cookie_file):
            raise ValueError("找不到 YTDLP_COOKIE_FILE 指定的 Cookies 檔案")
        options["cookiefile"] = cookie_file
    elif browser:
        name, _, profile = browser.partition(":")
        options["cookiesfrombrowser"] = (name, profile or None)
    if shutil.which("deno"):
        options["js_runtimes"] = {"deno": {}}
    elif shutil.which("node"):
        options["js_runtimes"] = {"node": {}}
    return options


def _progress_hook(callback: Optional[ProgressCallback]):
    def report(status: dict) -> None:
        if callback is None:
            return
        state = status.get("status")
        if state == "finished":
            callback(0.98, "下載完成，正在處理檔案…")
            return
        if state != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        downloaded = status.get("downloaded_bytes") or 0
        fraction = min(0.97, downloaded / total) if total else 0.0
        speed = status.get("_speed_str", "").strip()
        eta = status.get("_eta_str", "").strip()
        detail = " · ".join(part for part in (speed, f"剩餘 {eta}" if eta else "") if part)
        callback(fraction, f"正在下載{f' · {detail}' if detail else '…'}")

    return report


def _find_output(folder: Path, extension: str) -> Path:
    matches = [
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() == f".{extension}" and not path.name.endswith(".part")
    ]
    if len(matches) != 1:
        raise RuntimeError("下載完成，但找不到輸出檔案")
    return matches[0]


def download_media(
    url: str,
    media_type: str,
    quality: str,
    progress_callback: Optional[ProgressCallback] = None,
) -> MediaDownloadResult:
    """Download a single URL into a unique temporary directory."""
    if media_type not in {"MP4", "MP3"}:
        raise ValueError("不支援的下載格式")
    allowed = {
        "MP4": {"最佳畫質", "1080p", "720p", "480p"},
        "MP3": {"最高品質", "320 kbps", "192 kbps", "128 kbps"},
    }
    if quality not in allowed[media_type]:
        raise ValueError("不支援的畫質或音質")
    if not url.strip():
        raise ValueError("請輸入 YouTube 網址")
    if not shutil.which("ffmpeg"):
        raise ValueError("下載及轉檔需要 FFmpeg，請先安裝並加入 PATH")

    folder = Path(tempfile.mkdtemp(prefix="youtube_monster_download_"))
    try:
        options = _common_options()
        options.update({
            "outtmpl": str(folder / "%(title).180B [%(id)s].%(ext)s"),
            "progress_hooks": [_progress_hook(progress_callback)],
        })
        if media_type == "MP4":
            height = None if quality == "最佳畫質" else int(quality[:-1])
            ceiling = f"[height<={height}]" if height else ""
            options.update({
                "format": f"bv*{ceiling}+ba/b{ceiling}",
                "merge_output_format": "mp4",
            })
            extension = "mp4"
        else:
            bitrate = {
                "最高品質": "0", "320 kbps": "320", "192 kbps": "192", "128 kbps": "128",
            }[quality]
            options.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }],
            })
            extension = "mp3"

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url.strip(), download=True)
        if not info or info.get("_type") in {"playlist", "multi_video"}:
            raise ValueError("請提供單一影片網址")
        output = _find_output(folder, extension)
        if progress_callback:
            progress_callback(1.0, "檔案準備完成")
        return MediaDownloadResult(
            path=str(output), title=info.get("title") or "YouTube download",
            extension=extension, size=output.stat().st_size,
        )
    except Exception as error:
        shutil.rmtree(folder, ignore_errors=True)
        if isinstance(error, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(_clean_error(error)) from error


def cleanup_media_download(path: str) -> None:
    """Remove one completed download and its dedicated temporary directory."""
    if not path:
        return
    folder = Path(path).parent
    if folder.name.startswith("youtube_monster_download_"):
        shutil.rmtree(folder, ignore_errors=True)
