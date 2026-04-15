"""
合併版：YouTube 留言抓取 + Whisper 語音轉錄工具
- Tab 1: 留言抓取、文字雲、高頻詞分析 (cloud.py)
- Tab 2: 影片音訊下載 + Faster-Whisper 語音轉錄 (whisper.py)
"""

import logging
import os
import re
import tempfile
from collections import Counter
from io import BytesIO

import jieba
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import yt_dlp
from faster_whisper import WhisperModel
from googleapiclient.discovery import build
from wordcloud import STOPWORDS, WordCloud

# ── 全域設定 ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)

FONT_PATH = "C:/Windows/Fonts/msjh.ttc"
fm.fontManager.addfont(FONT_PATH)
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

API_KEY = "AIzaSyCEzWvL9Zg6HXcPnC94JM_yA6ueP0trFWY"


# ══════════════════════════════════════════════════════════════════
#  共用工具
# ══════════════════════════════════════════════════════════════════
def get_video_id(url: str) -> str:
    if "shorts/" in url:
        return url.split("shorts/")[1].split("?")[0]
    elif "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("/")[-1].split("?")[0]
    return url


# ══════════════════════════════════════════════════════════════════
#  Tab 1：留言抓取相關函式  (cloud.py)
# ══════════════════════════════════════════════════════════════════
def get_video_comments(video_id: str):
    youtube = build("youtube", "v3", developerKey=API_KEY)
    all_data = []
    nextPageToken = None
    status_placeholder = st.empty()

    try:
        while True:
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=100,
                pageToken=nextPageToken,
                textFormat="plainText",
            )
            response = request.execute()

            for item in response["items"]:
                top = item["snippet"]["topLevelComment"]["snippet"]
                all_data.append(
                    {
                        "類型": "頂層留言",
                        "使用者": top["authorDisplayName"],
                        "內容": top["textDisplay"],
                        "點讚": top["likeCount"],
                        "時間": top["publishedAt"],
                    }
                )

                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        rep = reply["snippet"]
                        all_data.append(
                            {
                                "類型": "└ 留言回覆",
                                "使用者": rep["authorDisplayName"],
                                "內容": rep["textDisplay"],
                                "點讚": rep["likeCount"],
                                "時間": rep["publishedAt"],
                            }
                        )

            status_placeholder.info(f"🚀 已抓取 {len(all_data)} 筆資料...")
            nextPageToken = response.get("nextPageToken")
            if not nextPageToken:
                break

        status_placeholder.empty()
        return all_data
    except Exception as e:
        st.error(f"發生錯誤: {e}")
        return None


def generate_wordcloud(df: pd.DataFrame):
    # ── 文字清理 ──────────────────────────────────────────
    all_text = " ".join(df["內容"].astype(str).tolist())
    all_text = re.sub(r"http\S+|www\S+", "", all_text)
    all_text = re.sub(r"[^\w\s\u3040-\u30ff\u4e00-\u9fff]", " ", all_text)

    # ── Stopwords ─────────────────────────────────────────
    custom_stopwords = set(STOPWORDS)
    custom_stopwords.update(
        [
            "的", "了", "是", "我", "你", "他", "她", "它", "們",
            "在", "也", "都", "就", "和", "有", "不", "這", "那",
            "一", "嗎", "啊", "吧", "哦", "哈", "好", "說", "來",
            "去", "會", "要", "可以", "因為", "所以", "但是", "還是",
            "如果", "這個", "那個", "什麼", "怎麼", "為什麼", "Reply",
            "replies", "reply", "https", "www", "com", "the", "to",
            "and", "of", "is", "it", "in", "that", "this",
        ]
    )

    # ── jieba 分詞（WordCloud 和 Bar Chart 共用）──────────
    words = list(jieba.cut(all_text, cut_all=False))
    words_filtered = [w.strip() for w in words if len(w.strip()) > 1]
    segmented = " ".join(words_filtered)

    # ── 產生 WordCloud（高解析度）────────────────────────
    wc = WordCloud(
        font_path=FONT_PATH,
        width=2400,
        height=1200,
        scale=2,
        background_color="white",
        max_words=200,
        stopwords=custom_stopwords,
        collocations=False,
        prefer_horizontal=0.7,
        min_font_size=10,
        max_font_size=160,
        colormap="tab20",
        random_state=42,
        regexp=r"[\w\u3040-\u30ff\u4e00-\u9fff]+",
    ).generate(segmented)

    # ── 顯示 Word Cloud ───────────────────────────────────
    st.subheader("☁️ 留言 Word Cloud")
    fig, ax = plt.subplots(figsize=(16, 8), dpi=150)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    plt.tight_layout(pad=0)
    st.pyplot(fig)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    buf.seek(0)
    st.download_button(
        label="📥 下載高解析度 Word Cloud PNG",
        data=buf,
        file_name="wordcloud_HQ.png",
        mime="image/png",
    )
    plt.close(fig)

    # ── Top 20 高頻詞（真實出現次數）─────────────────────
    st.subheader("📊 Top 20 高頻詞")
    words_for_count = [w for w in words_filtered if w not in custom_stopwords]
    word_count = Counter(words_for_count)
    top20 = word_count.most_common(20)

    if top20:
        chart_df = pd.DataFrame(top20, columns=["詞語", "出現次數"])
        st.dataframe(
            chart_df.style.bar(subset=["出現次數"], color="#4c9be8", vmin=0),
            width="stretch",
            hide_index=True,
        )


# ══════════════════════════════════════════════════════════════════
#  Tab 2：Whisper 語音轉錄相關函式  (whisper.py)
# ══════════════════════════════════════════════════════════════════
@st.cache_resource
def load_whisper_model() -> WhisperModel:
    """載入並快取 Whisper 模型（只初始化一次，避免每次重新載入）"""
    return WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")


def download_audio(youtube_url: str, base_path: str) -> str:
    """透過 yt-dlp 下載音訊並轉成 WAV，回傳 wav 路徑"""
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "outtmpl": base_path,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return base_path + ".wav"


def transcribe_audio(wav_path: str):
    """使用 Faster-Whisper 轉錄音訊，回傳 (segments, info)"""
    whisper_model = load_whisper_model()
    segments, info = whisper_model.transcribe(
        wav_path,
        # language="zh",          # 若確定是中文可取消此行的註解
        # task="translate",       # 若需翻成英文可取消此行的註解
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=1000),
        condition_on_previous_text=False,
        temperature=0.0,           # 關閉多溫度重試，避免卡死
        beam_size=1,               # 貪婪搜索，極大化推論速度
        initial_prompt="這是一段演講與對話。",
    )
    return segments, info


# ══════════════════════════════════════════════════════════════════
#  Streamlit 主介面
# ══════════════════════════════════════════════════════════════════

# --- Session State 初始化 ---
_defaults = {
    "running": False,
    "result_df": None,
    "result_video_id": None,
    "whisper_running": False,
    "transcript_lines": None,
    "transcript_info": None,
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def start_comment_fetch():
    st.session_state.running = True
    st.session_state.result_df = None


def start_whisper():
    st.session_state.whisper_running = True
    st.session_state.transcript_lines = None
    st.session_state.transcript_info = None


st.set_page_config(page_title="YouTube 怪獸", page_icon="🎬", layout="wide")
st.title("🎬 YouTube 怪獸")

tab1, tab2 = st.tabs(["📊留言抓取 & 文字雲", "🎙️語音轉錄(Whisper)"])


# ── Tab 1：留言抓取 ────────────────────────────────────────────
with tab1:
    st.header("🎥 YouTube 留言抓取tool")
    st.write("輸入影片網址，自動抓取**所有**留言（包含回覆）並匯出。")

    url_input = st.text_input(
        "請貼上 YouTube 網址:",
        placeholder="https://www.youtube.com/watch?v=...",
        disabled=st.session_state.running,
        key="comment_url",
    )

    st.button(
        "開始執行抓取",
        disabled=st.session_state.running,
        on_click=start_comment_fetch,
    )

    if st.session_state.running:
        if not url_input:
            st.warning("請先輸入網址！")
            st.session_state.running = False
        else:
            v_id = get_video_id(url_input)
            with st.spinner(f"正在深度抓取影片 ID: {v_id} 的全部留言..."):
                data = get_video_comments(v_id)
            if data:
                st.session_state.result_df = pd.DataFrame(data)
                st.session_state.result_video_id = v_id
            st.session_state.running = False
            st.rerun()

    if st.session_state.result_df is not None:
        df = st.session_state.result_df
        v_id = st.session_state.result_video_id

        st.success(f"✅ 抓取完成！總計（含回覆）共 {len(df)} 筆資料。")
        st.dataframe(df, width="stretch")

        csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button(
            label="📥 下載完整 CSV 檔案",
            data=csv,
            file_name=f"comments_{v_id}.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("📋 複製所有留言內容")
        all_comments_text = "\n".join(df["內容"].astype(str).tolist())
        st.text_area(
            label="所有留言內容（可全選後複製）",
            value=all_comments_text,
            height=300,
        )
        st.caption("💡 點入文字框後按 Ctrl+A 全選，再按 Ctrl+C 複製全部內容。")

        generate_wordcloud(df)


# ── Tab 2：Whisper 語音轉錄 ───────────────────────────────────
with tab2:
    st.header("🎙️ YouTube 影片語音轉錄工具")
    st.write(
        "輸入影片網址，自動下載音訊並使用 **Faster-Whisper large-v3-turbo** 進行轉錄，"
        "支援 99 種語言。"
    )

    whisper_url = st.text_input(
        "請貼上 YouTube 網址:",
        placeholder="https://www.youtube.com/watch?v=...",
        disabled=st.session_state.whisper_running,
        key="whisper_url",
    )

    st.button(
        "開始轉錄",
        disabled=st.session_state.whisper_running,
        on_click=start_whisper,
    )

    if st.session_state.whisper_running:
        if not whisper_url:
            st.warning("請先輸入網址！")
            st.session_state.whisper_running = False
        else:
            with st.spinner("⬇️ 正在下載音訊..."):
                tmp_base = os.path.join(tempfile.gettempdir(), "temp_audio")
                wav_path = download_audio(whisper_url, tmp_base)

            with st.spinner("🤖 正在載入模型並轉錄（長影片需要幾分鐘）..."):
                segments, info = transcribe_audio(wav_path)
                lines = [
                    f"[{seg.start:.2f}s -> {seg.end:.2f}s] {seg.text}"
                    for seg in segments
                ]

            st.session_state.transcript_lines = lines
            st.session_state.transcript_info = info
            st.session_state.whisper_running = False

            if os.path.exists(wav_path):
                os.remove(wav_path)

            st.rerun()

    if st.session_state.transcript_lines is not None:
        info = st.session_state.transcript_info
        lines = st.session_state.transcript_lines

        st.success(
            f"✅ 轉錄完成！預估語言：**{info.language}**，"
            f"準確率：{info.language_probability:.2%}"
        )

        transcript_text = "\n".join(lines)
        st.text_area("📄 轉錄結果", value=transcript_text, height=400)
        st.caption("💡 點入文字框後按 Ctrl+A 全選，再按 Ctrl+C 複製全部內容。")

        st.download_button(
            label="📥 下載轉錄文字 TXT",
            data=transcript_text.encode("utf-8"),
            file_name="transcript.txt",
            mime="text/plain",
        )
