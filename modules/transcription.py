"""
Transcription Module
語音轉錄和音訊下載邏輯
"""

import logging
import os
import shutil
import tempfile
from threading import Lock
from time import perf_counter
from typing import Callable, Tuple, Optional
from uuid import uuid4

import yt_dlp
from faster_whisper import BatchedInferencePipeline, WhisperModel

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
        # Streamlit shares this resource between reruns and browser sessions.
        self._lock = Lock()
    
    def load_model(self) -> None:
        """載入 Whisper 模型"""
        if self.model is not None:
            return
        try:
            started = perf_counter()
            logger.info(f"正在載入模型: {self.model_name}")
            self.model = WhisperModel(
                self.model_name,
                device="cuda",
                compute_type="float16"
            )
            logger.info("✓ 模型載入成功，耗時 %.1f 秒", perf_counter() - started)
        except Exception as e:
            logger.error(f"✗ 模型載入失敗: {str(e)}")
            raise TranscriptionError(f"無法載入 Whisper 模型: {str(e)}")
    
    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        batch_size: int = 4,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple:
        """
        轉錄音訊
        
        Args:
            audio_path: 音訊文件路徑
            language: 指定語言（如 'zh'、'en'）
            batch_size: 同時辨識的音訊區塊數；1 使用原本的逐段模式
            progress_callback: 回報進度 (0–1) 與目前階段
        
        Returns:
            (segments, info) 元組
        
        Raises:
            TranscriptionError: 轉錄失敗
        """
        if batch_size < 1:
            raise ValueError("batch_size 必須大於 0")

        def report(fraction, message):
            if progress_callback is not None:
                progress_callback(fraction, message)

        report(0.0, "等待轉錄資源…")
        with self._lock:
            try:
                if self.model is None:
                    report(0.0, "載入語音模型…（首次執行需要較久）")
                    self.load_model()
                started = perf_counter()
                while True:
                    try:
                        report(0.0, "音訊解碼、語音偵測與前處理中…")
                        logger.info("正在轉錄: %s，batch_size=%d", audio_path, batch_size)
                        # Use a fresh pipeline per attempt: it has mutable timestamp state.
                        engine = (BatchedInferencePipeline(model=self.model)
                                  if batch_size > 1 else self.model)
                        options = {"batch_size": batch_size} if batch_size > 1 else {}
                        segments, info = engine.transcribe(
                            audio_path,
                            language=language,
                            vad_filter=True,
                            vad_parameters=dict(min_silence_duration_ms=1000),
                            condition_on_previous_text=False,
                            temperature=0.0,
                            beam_size=1,
                            without_timestamps=False,
                            initial_prompt="這是一段演講與對話。",
                            **options,
                        )
                        report(0.0, "前處理完成，開始辨識語音…")
                        result = []
                        last_report = 0.0
                        # faster-whisper returns a lazy generator. Inference and GPU
                        # errors happen here, so completion must be logged afterwards.
                        for segment in segments:
                            result.append(segment)
                            now = perf_counter()
                            if now - last_report >= 0.5:
                                fraction = min(0.99, segment.end / info.duration) if info.duration else 0.0
                                report(fraction, f"已處理至 {segment.end / 60:.1f} / {info.duration / 60:.1f} 分鐘")
                                last_report = now
                        elapsed = perf_counter() - started
                        logger.info("✓ 轉錄完成，語言: %s，%d 段，耗時 %.1f 秒",
                                    info.language, len(result), elapsed)
                        report(1.0, f"轉錄完成，耗時 {elapsed:.1f} 秒")
                        return result, info
                    except RuntimeError as exc:
                        message = str(exc).lower()
                        if batch_size <= 1 or not any(
                            marker in message for marker in ("out of memory", "cuda_error_out_of_memory")
                        ):
                            raise
                        batch_size = max(1, batch_size // 2)
                        logger.warning("GPU 記憶體不足，改用 batch_size=%d 從頭重試", batch_size)
                        report(0.0, f"GPU 記憶體不足，降低批次大小至 {batch_size} 從頭重試…")
            except Exception as e:
                logger.error(f"✗ 轉錄失敗: {str(e)}")
                raise TranscriptionError(f"語音轉錄失敗: {str(e)}") from e


def download_audio(youtube_url: str, base_path: Optional[str] = None) -> Tuple[str, str]:
    """
    從 YouTube 下載音訊
    
    Args:
        youtube_url: YouTube 視頻 URL
        base_path: 輸出文件基礎路徑（不含副檔名）
    
    Returns:
        (下載的原始音訊文件路徑, 影片標題)；由 Faster-Whisper 直接解碼
    
    Raises:
        AudioDownloadError: 下載失敗
    """
    try:
        if base_path is None:
            base_path = os.path.join(tempfile.gettempdir(), f"yt_audio_{uuid4().hex}")
        
        logger.info(f"正在下載音訊: {youtube_url}")
        
        ydl_opts = {
            "format": "bestaudio/best",
            # PyAV in faster-whisper decodes WebM/M4A directly. Avoid a full
            # intermediate WAV conversion and its disk write/read.
            "outtmpl": os.fspath(base_path) + ".%(ext)s",
            "noplaylist": True,
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
            audio_path = ydl.prepare_filename(info)
        
        if not os.path.isfile(audio_path):
            raise AudioDownloadError("未生成音訊文件")
        
        logger.info(f"✓ 音訊下載成功: {audio_path}")
        return audio_path, (info.get("title") or "transcript")
    
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
