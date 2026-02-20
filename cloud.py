import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
from wordcloud import WordCloud, STOPWORDS
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import jieba
from collections import Counter
import re
from io import BytesIO

# ✅ 字型設定必須放最頂端
FONT_PATH = "C:/Windows/Fonts/msjh.ttc"
fm.fontManager.addfont(FONT_PATH)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# --- 設定區 ---
API_KEY = 'AIzaSyCEzWvL9Zg6HXcPnC94JM_yA6ueP0trFWY'


def get_video_id(url):
    if 'shorts/' in url:
        return url.split('shorts/')[1].split('?')[0]
    elif 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('/')[-1].split('?')[0]
    return url


def get_video_comments(video_id):
    youtube = build('youtube', 'v3', developerKey=API_KEY)
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
                textFormat="plainText"
            )
            response = request.execute()

            for item in response['items']:
                top = item['snippet']['topLevelComment']['snippet']
                all_data.append({
                    "類型": "頂層留言",
                    "使用者": top['authorDisplayName'],
                    "內容": top['textDisplay'],
                    "點讚": top['likeCount'],
                    "時間": top['publishedAt']
                })

                if 'replies' in item:
                    for reply in item['replies']['comments']:
                        rep = reply['snippet']
                        all_data.append({
                            "類型": "└ 留言回覆",
                            "使用者": rep['authorDisplayName'],
                            "內容": rep['textDisplay'],
                            "點讚": rep['likeCount'],
                            "時間": rep['publishedAt']
                        })

            status_placeholder.info(f"🚀 已抓取 {len(all_data)} 筆資料...")
            nextPageToken = response.get('nextPageToken')
            if not nextPageToken:
                break

        status_placeholder.empty()
        return all_data
    except Exception as e:
        st.error(f"發生錯誤: {e}")
        return None


def generate_wordcloud(df):
    # ── 文字清理 ──────────────────────────────────────────
    all_text = " ".join(df["內容"].astype(str).tolist())
    all_text = re.sub(r'http\S+|www\S+', '', all_text)
    all_text = re.sub(r'[^\w\s\u3040-\u30ff\u4e00-\u9fff]', ' ', all_text)

    # ── Stopwords ─────────────────────────────────────────
    custom_stopwords = set(STOPWORDS)
    custom_stopwords.update([
        "的", "了", "是", "我", "你", "他", "她", "它", "們",
        "在", "也", "都", "就", "和", "有", "不", "這", "那",
        "一", "嗎", "啊", "吧", "哦", "哈", "好", "說", "來",
        "去", "會", "要", "可以", "因為", "所以", "但是", "還是",
        "如果", "這個", "那個", "什麼", "怎麼", "為什麼", "Reply",
        "replies", "reply", "https", "www", "com", "the", "to",
        "and", "of", "is", "it", "in", "that", "this"
    ])

    # ── jieba 分詞（只做一次，WordCloud 和 Bar Chart 共用）──
    words = list(jieba.cut(all_text, cut_all=False))
    words_filtered = [w.strip() for w in words if len(w.strip()) > 1]
    segmented = " ".join(words_filtered)

    # ── 產生 WordCloud（高解析度）────────────────────────
    wc = WordCloud(
        font_path=FONT_PATH,
        width=2400,               # ✅ 高解析度畫布
        height=1200,
        scale=2,                  # ✅ 文字邊緣更平滑
        background_color="white",
        max_words=200,
        stopwords=custom_stopwords,
        collocations=False,
        prefer_horizontal=0.7,
        min_font_size=10,
        max_font_size=160,
        colormap="tab20",
        random_state=42,
        regexp=r"[\w\u3040-\u30ff\u4e00-\u9fff]+"
    ).generate(segmented)

    # ── 顯示 Word Cloud ───────────────────────────────────
    st.subheader("☁️ 留言 Word Cloud")
    fig, ax = plt.subplots(figsize=(16, 8), dpi=150)   # ✅ 高 DPI
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    plt.tight_layout(pad=0)
    st.pyplot(fig)

    # ✅ 下載高解析度 PNG（300 DPI）
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches='tight')
    buf.seek(0)
    st.download_button(
        label="📥 下載高解析度 Word Cloud PNG",
        data=buf,
        file_name="wordcloud_HQ.png",
        mime="image/png"
    )
    plt.close(fig)

    # ── Top 20 高頻詞（真實出現次數）─────────────────────
    st.subheader("📊 Top 20 高頻詞")

    words_for_count = [
        w for w in words_filtered
        if w not in custom_stopwords
    ]
    word_count = Counter(words_for_count)
    top20 = word_count.most_common(20)

    if top20:
        chart_df = pd.DataFrame(top20, columns=["詞語", "出現次數"])

        st.dataframe(
            chart_df.style.bar(
                subset=["出現次數"],   # ✅ 只在「出現次數」欄顯示長條
                color="#4c9be8",       # ✅ 長條顏色
                vmin=0
            ),
            width='stretch',
            hide_index=True            # ✅ 隱藏左側 index 數字
        )
# --- 初始化 Session State ---
if 'running' not in st.session_state:
    st.session_state.running = False
if 'result_df' not in st.session_state:
    st.session_state.result_df = None
if 'result_video_id' not in st.session_state:
    st.session_state.result_video_id = None


def start_running():
    st.session_state.running = True
    st.session_state.result_df = None


# --- Streamlit 網頁介面 ---
st.set_page_config(page_title="YouTube 留言抓取器", page_icon="📊", layout="wide")
st.title("🎥 YouTube 留言全部抓取工具")
st.write("輸入影片網址，自動抓取**所有**留言（包含回覆）並匯出。")

url_input = st.text_input(
    "請貼上 YouTube 網址:",
    placeholder="https://www.youtube.com/watch?v=...",
    disabled=st.session_state.running
)

st.button("開始執行抓取", disabled=st.session_state.running, on_click=start_running)

# --- 執行邏輯 ---
if st.session_state.running:
    if not url_input:
        st.warning("請先輸入網址！")
        st.session_state.running = False
    else:
        v_id = get_video_id(url_input)
        with st.spinner(f'正在深度抓取影片 ID: {v_id} 的全部留言...'):
            data = get_video_comments(v_id)
            if data:
                st.session_state.result_df = pd.DataFrame(data)
                st.session_state.result_video_id = v_id
        st.session_state.running = False
        st.rerun()

# --- 結果顯示區 ---
if st.session_state.result_df is not None:
    df = st.session_state.result_df
    v_id = st.session_state.result_video_id

    st.success(f"✅ 抓取完成！總計（含回覆）共 {len(df)} 筆資料。")
    st.dataframe(df, width='stretch')

    csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button(
        label="📥 下載完整 CSV 檔案",
        data=csv,
        file_name=f"comments_{v_id}.csv",
        mime="text/csv",
    )

    st.divider()
    generate_wordcloud(df)
