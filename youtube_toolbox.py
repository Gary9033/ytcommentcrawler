"""
YouTube 怪獸 - European Minimal Design Edition
YouTube 留言抓取 + Whisper 語音轉錄工具
"""

import logging
from collections import Counter
from io import BytesIO
from typing import Optional

import jieba
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from wordcloud import STOPWORDS, WordCloud

from modules import (
    load_css,
    info_box,
    extract_video_id,
    fetch_video_comments,
    clean_text,
    get_user_friendly_message,
    WhisperTranscriber,
    download_audio,
    format_transcription,
    cleanup_audio,
)

# ── 全域設定 ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_css()

st.set_page_config(
    page_title="YouTube 怪獸",
    page_icon="🎬",
    layout="wide"
)

FONT_PATH = "C:/Windows/Fonts/msjh.ttc"
try:
    fm.fontManager.addfont(FONT_PATH)
    plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
except:
    pass

API_KEY = "AIzaSyCEzWvL9Zg6HXcPnC94JM_yA6ueP0trFWY"


def generate_wordcloud(df):
    """生成文字雲"""
    try:
        all_text = " ".join(df["內容"].astype(str).tolist())
        all_text = clean_text(all_text)
        
        custom_stopwords = set(STOPWORDS)
        custom_stopwords.update([
            "的", "了", "是", "我", "你", "他", "她", "它", "們",
            "在", "也", "都", "就", "和", "有", "不", "這", "那",
        ])
        
        words = list(jieba.cut(all_text, cut_all=False))
        words_filtered = [w.strip() for w in words if len(w.strip()) > 1]
        segmented = " ".join(words_filtered)
        
        st.subheader("☁️ 留言文字雲")
        
        wc = WordCloud(
            font_path=FONT_PATH,
            width=2400,
            height=1200,
            background_color="white",
            max_words=200,
            stopwords=custom_stopwords,
        ).generate(segmented)
        
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
        plt.close(fig)
        
        st.subheader("📊 Top 20 高頻詞")
        words_for_count = [w for w in words_filtered if w not in custom_stopwords]
        word_count = Counter(words_for_count)
        top20 = word_count.most_common(20)
        
        if top20:
            chart_df = pd.DataFrame(top20, columns=["詞語", "出現次數"])
            st.dataframe(chart_df)
        
    except Exception as e:
        info_box(f"文字雲失敗: {str(e)}", box_type="error")


_whisper_transcriber = None

def get_transcriber():
    """獲取 Whisper 實例"""
    global _whisper_transcriber
    if _whisper_transcriber is None:
        _whisper_transcriber = WhisperTranscriber("large-v3-turbo")
    return _whisper_transcriber


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


def start_whisper():
    st.session_state.whisper_running = True


st.title("🎬 YouTube 怪獸")
tab1, tab2 = st.tabs(["📊 留言", "🎙️ 語音"])

with tab1:
    st.header("留言抓取")
    url = st.text_input("YouTube 網址:", disabled=st.session_state.running, key="url")
    
    if st.button("🚀 抓取", on_click=start_comment_fetch):
        pass
    
    if st.session_state.running:
        if not url:
            st.warning("請輸入網址")
            st.session_state.running = False
        else:
            try:
                v_id = extract_video_id(url)
                with st.spinner("抓取中..."):
                    data = fetch_video_comments(v_id, API_KEY)
                if data:
                    st.session_state.result_df = pd.DataFrame(data)
                    st.session_state.result_video_id = v_id
                st.session_state.running = False
                st.rerun()
            except Exception as e:
                st.error(f"失敗: {str(e)}")
                st.session_state.running = False
    
    if st.session_state.result_df is not None:
        df = st.session_state.result_df
        st.success(f"✅ 完成！{len(df)} 筆")
        st.dataframe(df)
        
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 CSV", csv, f"comments.csv", "text/csv")
        
        generate_wordcloud(df)

with tab2:
    st.header("語音轉錄")
    url = st.text_input("YouTube 網址:", disabled=st.session_state.whisper_running, key="whisper")
    
    if st.button("🎤 轉錄", on_click=start_whisper):
        pass
    
    if st.session_state.whisper_running:
        if not url:
            st.warning("請輸入網址")
            st.session_state.whisper_running = False
        else:
            audio_path = None
            try:
                v_id = extract_video_id(url)
                with st.spinner("下載中..."):
                    audio_path = download_audio(v_id, API_KEY)
                with st.spinner("轉錄中..."):
                    tr = get_transcriber()
                    segments, info = tr.transcribe(audio_path)
                    st.session_state.transcript_lines = segments
                    st.session_state.transcript_info = info
                st.session_state.whisper_running = False
                st.success("✅ 完成！")
            except Exception as e:
                st.error(f"失敗: {str(e)}")
                st.session_state.whisper_running = False
            finally:
                # 完成後刪除臨時音檔
                if audio_path:
                    cleanup_audio(audio_path)
    
    if st.session_state.transcript_lines:
        lines = st.session_state.transcript_lines
        info = st.session_state.transcript_info if st.session_state.transcript_info else {}
        
        st.subheader("📊 轉錄資訊")
        if info:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                lang = str(info.language).upper() if hasattr(info, 'language') else 'Unknown'
                st.metric("🗣️ 語言", lang)
            
            with col2:
                duration = f"{info.duration:.1f}s" if hasattr(info, 'duration') else "N/A"
                st.metric("⏱️ 時長", duration)
            
            with col3:
                try:
                    char_count = sum(len(seg.text) for seg in lines)
                except:
                    char_count = 0
                st.metric("📝 字數", char_count)
            
            with col4:
                # 計算語言檢測準確度 (基於語音活動概率)
                try:
                    if lines:
                        speech_probs = []
                        for seg in lines:
                            if hasattr(seg, 'no_speech_prob'):
                                quality = (1 - seg.no_speech_prob) * 100
                                speech_probs.append(quality)
                        
                        if speech_probs:
                            avg_quality = sum(speech_probs) / len(speech_probs)
                            st.metric("🎯 檢測準確度", f"{avg_quality:.1f}%")
                        else:
                            st.metric("🎯 檢測準確度", "N/A")
                    else:
                        st.metric("🎯 檢測準確度", "N/A")
                except Exception as e:
                    st.metric("🎯 檢測準確度", "N/A")
        
        st.subheader("📄 轉錄內容")
        
        try:
            text = "\n".join([seg.text for seg in lines])
        except AttributeError:
            text = "\n".join([str(seg) for seg in lines])
        
        st.text_area("轉錄", text, height=300)
        
        st.subheader("📥 下載選項")
        col_dl1, col_dl2, col_dl3 = st.columns(3)
        
        with col_dl1:
            st.download_button("📥 TXT", text, "transcript.txt", "text/plain")
        
        with col_dl2:
            try:
                srt_lines = []
                for idx, seg in enumerate(lines, 1):
                    start_h = int(seg.start) // 3600
                    start_m = (int(seg.start) % 3600) // 60
                    start_s = int(seg.start) % 60
                    start_ms = int((seg.start % 1) * 1000)
                    end_h = int(seg.end) // 3600
                    end_m = (int(seg.end) % 3600) // 60
                    end_s = int(seg.end) % 60
                    end_ms = int((seg.end % 1) * 1000)
                    
                    start_fmt = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d}"
                    end_fmt = f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
                    srt_lines.append(f"{idx}\n{start_fmt} --> {end_fmt}\n{seg.text}\n")
                srt_content = "\n".join(srt_lines)
                st.download_button("📥 SRT", srt_content, "transcript.srt", "text/plain")
            except Exception as e:
                st.warning(f"SRT 生成失敗: {str(e)}")
        
        with col_dl3:
            import json
            try:
                json_data = json.dumps({
                    "info": {
                        "language": str(info.language) if hasattr(info, 'language') else None,
                        "duration": float(info.duration) if hasattr(info, 'duration') else None,
                    },
                    "segments": [
                        {"start": float(seg.start), "end": float(seg.end), "text": seg.text}
                        for seg in lines
                    ]
                }, ensure_ascii=False, indent=2)
                st.download_button("📥 JSON", json_data, "transcript.json", "application/json")
            except Exception as e:
                st.warning(f"JSON 生成失敗: {str(e)}")
