"""
Comment Processor Module
評論抓取、清理、統計和緩存邏輯
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd

from googleapiclient.discovery import build

from .exceptions import CommentFetchError, APIError, VideoIDExtractionError

logger = logging.getLogger(__name__)


class CommentCache:
    """簡單的記憶體中評論緩存"""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        初始化緩存
        
        Args:
            ttl_seconds: 緩存生存時間（秒）
        """
        self.cache: Dict[str, Tuple[List[Dict], datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    def get(self, video_id: str) -> Optional[List[Dict]]:
        """獲取緩存的評論"""
        if video_id in self.cache:
            data, timestamp = self.cache[video_id]
            if datetime.now() - timestamp < self.ttl:
                logger.info(f"✓ 從緩存返回評論 (video_id: {video_id})")
                return data
            else:
                del self.cache[video_id]
        return None
    
    def set(self, video_id: str, data: List[Dict]) -> None:
        """設置評論緩存"""
        self.cache[video_id] = (data, datetime.now())
        logger.info(f"✓ 評論已緩存 (video_id: {video_id}, 記錄數: {len(data)})")
    
    def clear(self) -> None:
        """清空所有緩存"""
        self.cache.clear()


# 全局緩存實例
_comment_cache = CommentCache(ttl_seconds=3600)


def extract_video_id(url: str) -> str:
    """
    從 YouTube URL 提取視頻 ID
    
    Args:
        url: YouTube 網址
    
    Returns:
        視頻 ID
    
    Raises:
        VideoIDExtractionError: 無法提取視頻 ID
    """
    try:
        if "shorts/" in url:
            return url.split("shorts/")[1].split("?")[0]
        elif "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("/")[-1].split("?")[0]
        else:
            raise VideoIDExtractionError()
    except (IndexError, AttributeError):
        raise VideoIDExtractionError(f"無效的 YouTube URL: {url}")


def fetch_video_comments(
    video_id: str,
    api_key: str,
    use_cache: bool = True
) -> List[Dict]:
    """
    抓取 YouTube 視頻評論
    
    Args:
        video_id: YouTube 視頻 ID
        api_key: Google API 金鑰
        use_cache: 是否使用緩存
    
    Returns:
        評論列表
    
    Raises:
        CommentFetchError: 評論抓取失敗
    """
    # 檢查緩存
    if use_cache:
        cached = _comment_cache.get(video_id)
        if cached is not None:
            return cached
    
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        all_data = []
        next_page_token = None
        
        while True:
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat="plainText",
            )
            response = request.execute()
            
            for item in response["items"]:
                top = item["snippet"]["topLevelComment"]["snippet"]
                all_data.append({
                    "類型": "頂層留言",
                    "使用者": top["authorDisplayName"],
                    "內容": top["textDisplay"],
                    "點讚": top["likeCount"],
                    "時間": top["publishedAt"],
                })
                
                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        rep = reply["snippet"]
                        all_data.append({
                            "類型": "└ 留言回覆",
                            "使用者": rep["authorDisplayName"],
                            "內容": rep["textDisplay"],
                            "點讚": rep["likeCount"],
                            "時間": rep["publishedAt"],
                        })
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        
        # 存入緩存
        if use_cache:
            _comment_cache.set(video_id, all_data)
        
        logger.info(f"✓ 成功抓取 {len(all_data)} 條評論")
        return all_data
    
    except Exception as e:
        logger.error(f"✗ 評論抓取失敗: {str(e)}")
        raise CommentFetchError(f"無法抓取評論: {str(e)}")


def clean_text(text: str) -> str:
    """
    清理文本
    
    Args:
        text: 原始文本
    
    Returns:
        清理後的文本
    """
    # 移除 URL
    text = re.sub(r"http\S+|www\S+", "", text)
    # 移除特殊字符，保留中文、英文、空格
    text = re.sub(r"[^\w\s\u3040-\u30ff\u4e00-\u9fff]", " ", text)
    # 移除多餘空格
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_statistics(df: pd.DataFrame) -> Dict:
    """
    獲取評論統計信息
    
    Args:
        df: 評論 DataFrame
    
    Returns:
        統計信息字典
    """
    return {
        "總評論數": len(df),
        "頂層評論": len(df[df["類型"] == "頂層留言"]),
        "回覆評論": len(df[df["類型"] == "└ 留言回覆"]),
        "平均點讚": int(df["點讚"].mean()),
        "最多點讚": df["點讚"].max(),
    }


def clear_cache() -> None:
    """清空評論緩存"""
    _comment_cache.clear()
    logger.info("✓ 評論緩存已清空")
