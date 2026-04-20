"""
Custom Exceptions Module
統一的異常定義
"""


class YouTubeMonsterException(Exception):
    """YouTube Monster 基礎異常類"""
    pass


class VideoIDExtractionError(YouTubeMonsterException):
    """無法從 URL 提取視頻 ID"""
    pass


class CommentFetchError(YouTubeMonsterException):
    """評論抓取失敗"""
    pass


class AudioDownloadError(YouTubeMonsterException):
    """音訊下載失敗"""
    pass


class TranscriptionError(YouTubeMonsterException):
    """語音轉錄失敗"""
    pass


class APIError(YouTubeMonsterException):
    """API 調用失敗（如 YouTube API）"""
    pass


def get_user_friendly_message(exception: Exception) -> str:
    """
    將技術異常轉換為用戶友好的消息
    
    Args:
        exception: 異常對象
    
    Returns:
        用戶友好的錯誤消息
    """
    error_messages = {
        VideoIDExtractionError: "❌ 無法識別 YouTube 網址，請檢查 URL 格式",
        CommentFetchError: "❌ 評論抓取失敗。可能是 API 配額已超或網路連接問題",
        AudioDownloadError: "❌ 音訊下載失敗。請檢查網址是否有效",
        TranscriptionError: "❌ 語音轉錄失敗。請檢查音訊文件或稍後重試",
        APIError: "❌ API 調用失敗。請稍後重試",
    }
    
    for exc_type, message in error_messages.items():
        if isinstance(exception, exc_type):
            return message
    
    return f"❌ 發生未知錯誤：{str(exception)}"
