"""Download platform CC tracks without downloading video or loading Whisper."""

import html
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError


class SubtitleRateLimitError(RuntimeError):
    """Raised when the platform temporarily throttles subtitle downloads."""


def _clean_error(error):
    return re.sub(r"\x1b\[[0-9;]*m", "", str(error)).strip()


def _original_automatic_captions(captions):
    """Exclude YouTube's translated caption aliases (URLs containing tlang)."""
    original = {}
    for language, entries in captions.items():
        urls = [entry.get("url", "") for entry in entries if entry.get("url")]
        if not urls or any("tlang" not in parse_qs(urlparse(url).query) for url in urls):
            original[language] = entries
    explicitly_original = {
        language: entries for language, entries in original.items()
        if language.lower().endswith("-orig")
    }
    return explicitly_original or original


def subtitle_options():
    options = {"skip_download": True, "noplaylist": True, "quiet": True}
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


def list_subtitles(url):
    with yt_dlp.YoutubeDL(subtitle_options()) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info or info.get("_type") in ("playlist", "multi_video"):
        raise ValueError("請提供單一影片網址")
    # yt-dlp exposes chat replay alongside subtitle tracks. It is not CC.
    manual = {key: entries for key, entries in (info.get("subtitles") or {}).items()
              if key != "live_chat"}
    automatic = {key: entries for key, entries in (info.get("automatic_captions") or {}).items()
                 if key != "live_chat"}
    return {
        "title": info.get("title") or "subtitles",
        "manual": manual,
        "automatic": _original_automatic_captions(automatic),
    }


def choose_subtitle_track(catalog, preferred_language=None):
    """Choose one original-language CC track, preferring manual and language matches."""
    preferred_base = str(preferred_language or "").lower().replace("_", "-").split("-")[0]

    def matching_track(source):
        tracks = catalog.get(source) or {}
        if not preferred_base:
            return None
        for language in sorted(tracks):
            language_base = language.lower().replace("_", "-").split("-")[0]
            if language_base == preferred_base and tracks[language]:
                return source, language
        return None

    for source in ("manual", "automatic"):
        match = matching_track(source)
        if match:
            return match
    for source in ("manual", "automatic"):
        tracks = catalog.get(source) or {}
        for language in sorted(tracks):
            if tracks[language]:
                return source, language
    return None


def srt_to_text(srt):
    lines = []
    for block in re.split(r"\n\s*\n", srt.replace("\r\n", "\n").strip()):
        cue = block.splitlines()
        if cue and cue[0].strip().isdigit():
            cue = cue[1:]
        if cue and "-->" in cue[0]:
            cue = cue[1:]
        text = html.unescape(re.sub(r"<[^>]+>", "", "\n".join(cue))).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def download_subtitle(url, source, language, output_format):
    if source not in ("manual", "automatic") or output_format not in ("SRT", "TXT"):
        raise ValueError("不支援的字幕來源或格式")
    if not shutil.which("ffmpeg"):
        raise ValueError("字幕格式轉換需要 FFmpeg，請先安裝並加入 PATH")
    with tempfile.TemporaryDirectory(prefix="cc_subtitles_") as folder:
        options = subtitle_options()
        options.update({
            "writesubtitles": source == "manual",
            "writeautomaticsub": source == "automatic",
            "subtitleslangs": [re.escape(language)],
            "subtitlesformat": "srt/vtt/best",
            "outtmpl": str(Path(folder) / "subtitle.%(ext)s"),
            "postprocessors": [{"key": "FFmpegSubtitlesConvertor", "format": "srt"}],
        })
        last_error = None
        for delay in (0, 2, 5):
            if delay:
                time.sleep(delay)
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.extract_info(url, download=True)
                last_error = None
                break
            except DownloadError as error:
                last_error = error
                if "429" not in str(error):
                    raise RuntimeError(_clean_error(error)) from error
        if last_error is not None:
            raise SubtitleRateLimitError(
                "YouTube 暫時限制字幕下載（HTTP 429）。程式已自動重試；請稍候 10～30 分鐘再試，"
                "或設定瀏覽器 Cookies 後重試。即時翻譯的自動字幕比原始語言字幕更容易被限制。"
            ) from last_error
        files = list(Path(folder).glob("*.srt"))
        if len(files) != 1:
            raise ValueError("未取得選定的字幕，請重新讀取字幕清單或選擇其他語言")
        srt = files[0].read_text(encoding="utf-8-sig")
        return srt if output_format == "SRT" else srt_to_text(srt)
