"""
YouTube Monster Modules Package
"""

from .ui_components import (
    load_css,
    header_section,
    input_card,
    action_button,
    progress_indicator,
    info_box,
    two_column_layout,
    data_display_table,
    section_divider,
    geometric_divider,
    labeled_metric,
    download_button_custom,
)

from .exceptions import (
    YouTubeMonsterException,
    VideoIDExtractionError,
    CommentFetchError,
    AudioDownloadError,
    TranscriptionError,
    APIError,
    get_user_friendly_message,
)

from .comment_processor import (
    extract_video_id,
    fetch_video_comments,
    clean_text,
    get_statistics,
    clear_cache,
)

from .transcription import (
    WhisperTranscriber,
    download_audio,
    format_transcription,
    cleanup_audio,
)

__all__ = [
    # UI Components
    "load_css",
    "header_section",
    "input_card",
    "action_button",
    "progress_indicator",
    "info_box",
    "two_column_layout",
    "data_display_table",
    "section_divider",
    "geometric_divider",
    "labeled_metric",
    "download_button_custom",
    # Exceptions
    "YouTubeMonsterException",
    "VideoIDExtractionError",
    "CommentFetchError",
    "AudioDownloadError",
    "TranscriptionError",
    "APIError",
    "get_user_friendly_message",
    # Comment Processing
    "extract_video_id",
    "fetch_video_comments",
    "clean_text",
    "get_statistics",
    "clear_cache",
    # Transcription
    "WhisperTranscriber",
    "download_audio",
    "format_transcription",
    "cleanup_audio",
]
