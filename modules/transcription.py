"""
Transcription Module
語音轉錄和音訊下載邏輯
"""

import logging
import os
import shutil
import tempfile
from typing import Tuple, Optional

import yt_dlp
from faster_whisper import WhisperModel

from .exceptions import AudioDownloadError, TranscriptionError

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Faster-Whisper 語音轉錄器"""
    
    def __init__(self, model_name: str = "large-v3-turbo"):
        """
        初始化轉錄器
        
        Args:
            model_name: Whisper 模型名稱
        """
        self.model_name = model_name
        self.model: Optional[WhisperModel] = None
    
    def load_model(self) -> None:
        """載入 Whisper 模型"""
        try:
            logger.info(f"正在載入模型: {self.model_name}")
            self.model = WhisperModel(
                self.model_name,
                device="cuda",
                compute_type="float16"
            )
            logger.info("✓ 模型載入成功")
        except Exception as e:
            logger.error(f"✗ 模型載入失敗: {str(e)}")
            raise TranscriptionError(f"無法載入 Whisper 模型: {str(e)}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None
    ) -> Tuple:
        """
        轉錄音訊
        
        Args:
            audio_path: 音訊文件路徑
            language: 指定語言（如 'zh'、'en'）
        
        Returns:
            (segments, info) 元組
        
        Raises:
            TranscriptionError: 轉錄失敗
        """
        if self.model is None:
            self.load_model()
        
        try:
            logger.info(f"正在轉錄: {audio_path}")
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=1000),
                condition_on_previous_text=False,
                temperature=0.0,
                beam_size=1,
                initial_prompt="這是一段演講與對話。",
            )
            logger.info(f"✓ 轉錄完成，語言: {info.language}")
            return list(segments), info
        except Exception as e:
            logger.error(f"✗ 轉錄失敗: {str(e)}")
            raise TranscriptionError(f"語音轉錄失敗: {str(e)}")


def download_audio(youtube_url: str, base_path: Optional[str] = None) -> Tuple[str, str]:
    """
    從 YouTube 下載音訊
    
    Args:
        youtube_url: YouTube 視頻 URL
        base_path: 輸出文件基礎路徑（不含副檔名）
    
    Returns:
        WAV 文件路徑
    
    Raises:
        AudioDownloadError: 下載失敗
    """
    try:
        if base_path is None:
            base_path = os.path.join(tempfile.gettempdir(), "yt_audio")
        
        logger.info(f"正在下載音訊: {youtube_url}")
        
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": base_path,
            "quiet": False,
            "no_warnings": False,
        }

        # Newer YouTube extraction requires a JavaScript runtime. Prefer
        # Deno (yt-dlp's default), but automatically use Node when Deno is
        # not installed on Windows.
        js_runtime = None
        if shutil.which("deno"):
            js_runtime = "deno"
        elif shutil.which("node"):
            js_runtime = "node"
        if js_runtime:
            ydl_opts["js_runtimes"] = {js_runtime: {}}
        else:
            logger.warning(
                "找不到 Deno 或 Node.js；請安裝其中一個以支援 YouTube EJS 驗證"
            )

        # YouTube may require an authenticated browser session when the
        # current IP is rate-limited or flagged as automated traffic. Do not
        # read browser cookies unless the user explicitly opts in through an
        # environment variable.
        cookie_file = os.getenv("YTDLP_COOKIE_FILE", "").strip()
        cookies_browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
        if cookie_file:
            if os.path.isfile(cookie_file):
                ydl_opts["cookiefile"] = cookie_file
                logger.info("使用 yt-dlp cookies 檔案下載音訊")
            else:
                logger.warning("找不到 YTDLP_COOKIE_FILE 指定的檔案: %s", cookie_file)
        elif cookies_browser:
            # Examples: chrome, edge, firefox, chrome:Profile 1
            browser_parts = cookies_browser.split(":", 1)
            browser_name = browser_parts[0].strip()
            browser_profile = browser_parts[1].strip() if len(browser_parts) == 2 else None
            ydl_opts["cookiesfrombrowser"] = (
                browser_name,
                browser_profile,
            )
            logger.info("使用 %s 瀏覽器 cookies 下載音訊", browser_name)
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
        
        wav_path = base_path + ".wav"
        
        if not os.path.exists(wav_path):
            raise AudioDownloadError("未生成 WAV 文件")
        
        logger.info(f"✓ 音訊下載成功: {wav_path}")
        return wav_path, (info.get("title") or "transcript")
    
    except Exception as e:
        logger.error(f"✗ 音訊下載失敗: {str(e)}")
        raise AudioDownloadError(f"無法下載音訊: {str(e)}")


def format_transcription(segments, info) -> str:
    """
    格式化轉錄結果
    
    Args:
        segments: 轉錄段落列表
        info: 轉錄信息
    
    Returns:
        格式化的轉錄文本
    """
    lines = [
        f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}"
        for seg in segments
    ]
    return "\n".join(lines)


def cleanup_audio(audio_path: str) -> None:
    """
    清理音訊文件
    
    Args:
        audio_path: 音訊文件路徑
    """
    try:
        if os.path.exists(audio_path):
            os.remove(audio_path)
            logger.info(f"✓ 清理音訊文件: {audio_path}")
    except Exception as e:
        logger.warning(f"⚠ 無法清理音訊文件: {str(e)}")
