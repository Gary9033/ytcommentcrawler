"""
YouTube 怪獸 - European Minimal Design Edition
YouTube 留言抓取 + Whisper 語音轉錄工具
"""

import logging
import json
import os
import re
from pathlib import Path
from collections import Counter
from io import BytesIO
from time import perf_counter
from typing import Optional

import jieba
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from wordcloud import STOPWORDS, WordCloud
from modules.subtitles import (
    choose_subtitle_track,
    download_subtitle,
    list_subtitles,
    srt_to_text,
)
from modules.media_downloader import (
    cleanup_media_download,
    download_media,
    fetch_video_title,
    youtube_thumbnail_url,
)

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

API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()


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


def render_copy_comments_button(df):
    """渲染一鍵複製全部留言的按鈕"""
    if "內容" not in df.columns:
        return

    comments = [
        comment.strip()
        for comment in df["內容"].dropna().astype(str)
        if comment.strip()
    ]
    if not comments:
        st.info("沒有可複製的留言內容")
        return

    comments_text = "\n".join(comments)
    comments_json = json.dumps(comments_text).replace("</", "<\\/")
    comments_count = len(comments)

    components.html(
        f"""
        <button id="copy-comments-btn" type="button">
            📋 複製全部留言
        </button>
        <span id="copy-comments-status" aria-live="polite"></span>
        <textarea id="copy-comments-source" aria-hidden="true"></textarea>
        <style>
            #copy-comments-btn {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-height: 38px;
                padding: 0 14px;
                border: 1px solid rgba(49, 51, 63, 0.2);
                border-radius: 6px;
                background: #ffffff;
                color: #31333f;
                font: 14px/1.2 sans-serif;
                cursor: pointer;
            }}
            #copy-comments-btn:hover {{
                border-color: rgba(49, 51, 63, 0.45);
            }}
            #copy-comments-status {{
                margin-left: 10px;
                color: #2e7d32;
                font: 14px/1.2 sans-serif;
            }}
            #copy-comments-source {{
                position: fixed;
                left: -9999px;
                top: 0;
                opacity: 0;
            }}
        </style>
        <script>
            const commentsText = {comments_json};
            const button = document.getElementById("copy-comments-btn");
            const status = document.getElementById("copy-comments-status");
            const source = document.getElementById("copy-comments-source");

            function copyWithSelectionFallback() {{
                source.value = commentsText;
                source.focus();
                source.select();
                const copied = document.execCommand("copy");
                source.blur();
                if (!copied) {{
                    throw new Error("copy command failed");
                }}
            }}

            async function copyComments() {{
                try {{
                    let copiedByClipboardApi = false;
                    if (navigator.clipboard && window.isSecureContext) {{
                        try {{
                            await navigator.clipboard.writeText(commentsText);
                            copiedByClipboardApi = true;
                        }} catch (error) {{
                            copiedByClipboardApi = false;
                        }}
                    }}
                    if (!copiedByClipboardApi) {{
                        copyWithSelectionFallback();
                    }}
                    status.style.color = "#2e7d32";
                    status.textContent = "已複製 {comments_count} 筆留言";
                    window.setTimeout(() => {{
                        status.textContent = "";
                    }}, 2200);
                }} catch (error) {{
                    status.textContent = "複製失敗，請手動選取或下載 CSV";
                    status.style.color = "#b3261e";
                }}
            }}

            button.addEventListener("click", copyComments);
        </script>
        """,
        height=52,
    )


@st.cache_resource
def get_transcriber():
    """跨 Streamlit 重跑共用模型，避免每次重新載入 GPU。"""
    return WhisperTranscriber("large-v3-turbo")


def safe_filename(name: str, fallback: str = "transcript") -> str:
    """將影片標題轉成 Windows 可用的檔名。"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .")
    return name[:180] or fallback


_defaults = {
    "running": False,
    "result_df": None,
    "result_video_id": None,
    "whisper_running": False,
    "transcript_lines": None,
    "transcript_info": None,
    "transcript_title": "transcript",
    "transcript_timings": None,
    "transcript_cc": None,
    "transcript_cc_error": None,
    "media_running": False,
    "media_result": None,
}
for key, val in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def start_comment_fetch():
    st.session_state.running = True


def start_whisper():
    st.session_state.whisper_running = True


@st.cache_data(ttl=600, show_spinner=False)
def get_preview_title(url: str):
    try:
        return fetch_video_title(url)
    except Exception:
        logger.warning("無法取得影片預覽標題", exc_info=True)
        return ""


def render_video_preview(url: str, title=None):
    """Show the video title above its thumbnail in every tab."""
    thumbnail_url = youtube_thumbnail_url(url)
    if thumbnail_url:
        title = get_preview_title(url.strip()) if title is None else title
        if title:
            st.subheader(title)
        else:
            st.caption("暫時無法取得影片標題")
        st.image(thumbnail_url, width="stretch")


def render_transcription_cc_preview(url: str):
    """Check CC before downloading audio; retain results only for this URL."""
    if not url.strip():
        st.session_state.pop("whisper_cc_preview", None)
        return
    saved = st.session_state.get("whisper_cc_preview")
    if (not saved or saved.get("url") != url
            or (not isinstance(saved.get("catalog"), dict) and not saved.get("error"))):
        saved = {"url": url, "catalog": None, "error": None, "result": None}
        try:
            with st.spinner("檢查影片 CC 字幕中…"):
                saved["catalog"] = list_subtitles(url)
                if not isinstance(saved["catalog"], dict):
                    raise ValueError("未取得有效的字幕清單，請重新檢查")
        except Exception as error:
            saved["error"] = str(error)
        # Publish only the completed lookup. A rerun must not reuse an
        # in-progress placeholder whose catalog is still None.
        st.session_state.whisper_cc_preview = saved
    catalog = saved.get("catalog") or {}
    render_video_preview(url, catalog.get("title"))
    if saved["error"]:
        st.warning(f"暫時無法確認 CC 字幕：{saved['error']}。你仍可使用 Whisper 轉錄。")
        if st.button("重新檢查 CC", key="whisper_cc_retry"):
            st.session_state.pop("whisper_cc_preview", None)
            st.rerun()
        return
    tracks = [
        (source, language)
        for source in ("manual", "automatic")
        for language, entries in sorted((catalog.get(source) or {}).items())
        if entries
    ]
    if not tracks:
        st.info("這部影片沒有可用的 CC 字幕，可以使用下方 Whisper 語音轉錄。")
        return
    st.success("✅ 這部影片已有 CC 字幕，可以直接使用，不必自行語音轉錄。")

    def track_label(track):
        source, language = track
        name = catalog[source][language][0].get("name") or language
        kind = "人工 CC" if source == "manual" else "自動 CC"
        return f"{kind} · {language} · {name}"

    track = st.selectbox(
        "可用 CC 字幕", tracks, format_func=track_label, key="whisper_cc_track",
    )
    if st.button("顯示 CC 字幕（不用轉錄）", key="whisper_cc_prepare"):
        saved["result"] = None
        try:
            with st.spinner("下載 CC 字幕中…"):
                srt = download_subtitle(url, *track, "SRT")
            saved["result"] = (track, srt, srt_to_text(srt))
        except Exception as error:
            st.warning(f"CC 字幕下載失敗：{error}。可稍後重試或使用 Whisper 轉錄。")
    result = saved["result"]
    if result and result[0] == track:
        st.text_area("平台 CC 字幕內容", result[2], height=250, key="whisper_cc_text")
        filename = f"{safe_filename(catalog['title'])}.{safe_filename(track[1])}"
        st.download_button("下載 CC TXT", result[2], f"{filename}.txt", "text/plain", key="whisper_cc_txt")
        st.download_button("下載 CC SRT", result[1], f"{filename}.srt", "text/plain", key="whisper_cc_srt")


st.title("🎬 YouTube 怪獸")
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 留言", "🎙️ 語音", "📄 CC 字幕下載", "📥 下載影片／音訊",
])

with tab1:
    st.header("留言抓取")
    url = st.text_input("YouTube 網址:", disabled=st.session_state.running, key="url")
    render_video_preview(url)
    
    if st.button("🚀 抓取", on_click=start_comment_fetch):
        pass
    
    if st.session_state.running:
        if not url:
            st.warning("請輸入網址")
            st.session_state.running = False
        elif not API_KEY:
            st.error("尚未設定 YOUTUBE_API_KEY，請先以環境變數提供 YouTube Data API 金鑰。")
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
        render_copy_comments_button(df)
        
        generate_wordcloud(df)

with tab2:
    st.header("語音轉錄")
    url = st.text_input("YouTube 網址:", disabled=st.session_state.whisper_running, key="whisper")
    render_transcription_cc_preview(url)
    col_language, col_batch = st.columns(2)
    with col_language:
        language_label = st.selectbox(
            "音訊語言", ["自動偵測", "中文", "英文", "日文", "韓文"],
            disabled=st.session_state.whisper_running,
            help="已知語言時可直接指定，省去自動語言偵測。",
        )
    with col_batch:
        batch_size = st.selectbox(
            "批次大小", [1, 2, 4, 8], index=2,
            disabled=st.session_state.whisper_running,
            help="同時辨識多段音訊以加快速度。6GB 顯卡可先試 4；記憶體不足會自動降低。1 使用原本逐段模式。",
        )
    
    if st.button("🎤 轉錄", on_click=start_whisper, key="whisper_start"):
        pass
    
    if st.session_state.whisper_running:
        if not url:
            st.warning("請輸入網址")
            st.session_state.whisper_running = False
        else:
            audio_path = None
            st.session_state.transcript_cc = None
            st.session_state.transcript_cc_error = None
            try:
                total_started = perf_counter()
                with st.spinner("下載中..."):
                    # yt-dlp needs the original YouTube URL.  The API key is
                    # only used for YouTube Data API comment requests and
                    # must not be passed as the audio output path.
                    audio_path, video_title = download_audio(url)
                download_seconds = perf_counter() - total_started
                transcription_started = perf_counter()
                progress = st.progress(0.0, text="準備轉錄…")
                with st.spinner("轉錄中..."):
                    tr = get_transcriber()
                    language = {"中文": "zh", "英文": "en", "日文": "ja", "韓文": "ko"}.get(language_label)
                    segments, info = tr.transcribe(
                        audio_path, language=language, batch_size=batch_size,
                        progress_callback=lambda fraction, message: progress.progress(fraction, text=message),
                    )
                    st.session_state.transcript_lines = segments
                    st.session_state.transcript_info = info
                    st.session_state.transcript_title = safe_filename(video_title)
                    st.session_state.transcript_timings = {
                        "download": download_seconds,
                        "transcription": perf_counter() - transcription_started,
                        "total": perf_counter() - total_started,
                    }
                try:
                    progress.progress(1.0, text="Whisper 完成，正在檢查平台 CC…")
                    with st.spinner("同步平台 CC 字幕中..."):
                        catalog = list_subtitles(url)
                        preferred_language = language or getattr(info, "language", None)
                        cc_track = choose_subtitle_track(catalog, preferred_language)
                        if cc_track:
                            cc_source, cc_language = cc_track
                            cc_srt = download_subtitle(url, cc_source, cc_language, "SRT")
                            st.session_state.transcript_cc = {
                                "source": cc_source,
                                "language": cc_language,
                                "srt": cc_srt,
                                "txt": srt_to_text(cc_srt),
                            }
                except Exception as cc_error:
                    logger.warning("Whisper 已完成，但平台 CC 取得失敗: %s", cc_error)
                    st.session_state.transcript_cc_error = str(cc_error)
                st.session_state.transcript_timings["total"] = perf_counter() - total_started
                progress.progress(1.0, text="轉錄與字幕準備完成")
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
        timings = st.session_state.transcript_timings
        if timings:
            st.caption(
                f"下載 {timings['download']:.1f} 秒 · 轉錄（含模型載入與前處理）"
                f" {timings['transcription']:.1f} 秒 · 總計 {timings['total']:.1f} 秒"
            )
        
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
            txt_filename = f"{st.session_state.get('transcript_title', 'transcript')}.txt"
            st.download_button("📥 TXT", text, txt_filename, "text/plain")
        
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

        cc_result = st.session_state.get("transcript_cc")
        if cc_result:
            source_label = "人工 CC" if cc_result["source"] == "manual" else "自動 CC"
            st.subheader("📄 平台 CC 字幕")
            st.caption(f"{source_label} · {cc_result['language']} · 與 Whisper 結果一併提供")
            cc_col1, cc_col2 = st.columns(2)
            cc_base = st.session_state.get("transcript_title", "transcript")
            with cc_col1:
                st.download_button(
                    "📥 平台 CC SRT", cc_result["srt"].encode("utf-8-sig"),
                    f"{cc_base}.{safe_filename(cc_result['language'])}.cc.srt",
                    "text/plain; charset=utf-8", key="whisper_cc_srt",
                )
            with cc_col2:
                st.download_button(
                    "📥 平台 CC TXT", cc_result["txt"].encode("utf-8-sig"),
                    f"{cc_base}.{safe_filename(cc_result['language'])}.cc.txt",
                    "text/plain; charset=utf-8", key="whisper_cc_txt",
                )
        elif st.session_state.get("transcript_cc_error"):
            st.caption(
                "Whisper 已完成；平台 CC 未能一併取得："
                f"{st.session_state.transcript_cc_error}"
            )

with tab3:
    st.header("CC 字幕下載")
    st.caption("下載平台提供的 CC，不進行語音辨識；不支援影片畫面內燒錄的字幕")
    cc_url = st.text_input("影片網址", key="cc_url").strip()
    render_video_preview(cc_url)
    if st.button("讀取字幕清單", key="cc_list"):
        st.session_state.pop("cc_catalog", None)
        st.session_state.pop("cc_result", None)
        if not cc_url:
            st.warning("請輸入影片網址")
        else:
            try:
                with st.spinner("讀取字幕中…"):
                    catalog = list_subtitles(cc_url)
                st.session_state.cc_catalog = (cc_url, catalog)
            except Exception as e:
                st.error(f"讀取字幕失敗：{e}")
    saved_catalog = st.session_state.get("cc_catalog")
    if saved_catalog and saved_catalog[0] == cc_url:
        catalog = saved_catalog[1]
        st.write(catalog["title"])
        source = st.radio(
            "字幕來源", ["manual", "automatic"],
            format_func=lambda value: "人工 CC（原始上傳）" if value == "manual" else "自動 CC（原始語音）",
            horizontal=True, key="cc_source",
        )
        tracks = {code: entries for code, entries in catalog[source].items() if entries}
        if not tracks:
            st.info("這部影片沒有此來源的原始字幕。可切換來源，或到「語音」分頁使用 Whisper 轉錄。")
        else:
            language = st.selectbox(
                "字幕語言", sorted(tracks), key=f"cc_language_{source}",
                format_func=lambda code: f"{code} · {tracks[code][0].get('name') or code}",
            )
            output_format = st.selectbox("下載格式", ["SRT", "TXT"], index=1, key="cc_format")
            selection = (cc_url, source, language, output_format)
            if st.button("轉換字幕檔", key="cc_prepare"):
                st.session_state.pop("cc_result", None)
                try:
                    with st.spinner("下載及轉換字幕中…"):
                        content = download_subtitle(*selection)
                    st.session_state.cc_result = (selection, content)
                except Exception as e:
                    st.error(f"字幕下載失敗：{e}")
            result = st.session_state.get("cc_result")
            if result and result[0] == selection:
                filename = f"{safe_filename(catalog['title'])}.{safe_filename(language)}.{output_format.lower()}"
                st.download_button(
                    f"下載 {output_format}", result[1].encode("utf-8-sig"), filename,
                    mime="text/plain; charset=utf-8", key="cc_download",
                )

with tab4:
    st.header("下載影片／音訊")
    st.caption("將單一 YouTube 影片儲存為 MP4，或擷取為 MP3")
    media_url = st.text_input(
        "影片網址", key="media_url", disabled=st.session_state.media_running,
        placeholder="https://www.youtube.com/watch?v=…",
    ).strip()
    render_video_preview(media_url)
    media_col_type, media_col_quality = st.columns(2)
    with media_col_type:
        media_type = st.segmented_control(
            "下載格式", ["MP4", "MP3"], default="MP4", key="media_type",
            disabled=st.session_state.media_running,
        ) or "MP4"
    qualities = (
        ["最佳畫質", "1080p", "720p", "480p"]
        if media_type == "MP4"
        else ["最高品質", "320 kbps", "192 kbps", "128 kbps"]
    )
    with media_col_quality:
        media_quality = st.selectbox(
            "畫質" if media_type == "MP4" else "MP3 音質",
            qualities, key=f"media_quality_{media_type}",
            disabled=st.session_state.media_running,
        )
    if media_type == "MP3":
        st.caption("MP3 碼率是轉檔設定；選擇 320 kbps 不會提高 YouTube 原始音訊的品質。")
    else:
        st.caption("指定畫質會選擇不高於該解析度的最佳版本；實際畫質依影片提供的格式而定。")

    media_selection = (media_url, media_type, media_quality)
    media_clicked = st.button("開始下載", key="media_prepare", type="primary")
    if media_clicked:
        st.session_state.media_running = True
        if not media_url:
            st.warning("請輸入 YouTube 網址")
            st.session_state.media_running = False
        else:
            old_result = st.session_state.get("media_result")
            if old_result:
                cleanup_media_download(old_result[1].path)
                st.session_state.media_result = None
            progress = st.progress(0.0, text="準備下載…")
            try:
                result = download_media(
                    media_url, media_type, media_quality,
                    progress_callback=lambda fraction, message: progress.progress(fraction, text=message),
                )
                st.session_state.media_result = (media_selection, result)
                st.success("檔案已準備完成")
            except Exception as error:
                st.error(f"下載失敗：{error}")
            finally:
                st.session_state.media_running = False

    saved_media = st.session_state.get("media_result")
    if saved_media and saved_media[0] == media_selection:
        result = saved_media[1]
        size_mb = result.size / (1024 * 1024)
        st.subheader(result.title)
        st.caption(f"{result.extension.upper()} · {size_mb:.1f} MB")
        with open(result.path, "rb") as media_file:
            st.download_button(
                f"儲存 {result.extension.upper()}", media_file,
                file_name=Path(result.path).name,
                mime="video/mp4" if result.extension == "mp4" else "audio/mpeg",
                key="media_save",
            )
    elif saved_media:
        st.info("設定已變更。請按「開始下載」準備新的檔案。")

    st.info("請只下載你有權保存或已取得授權的內容，並遵守 YouTube 使用條款。")
