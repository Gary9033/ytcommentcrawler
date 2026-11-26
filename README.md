# YouTube 怪獸 (YouTube Monster) 🚀
![License](https://img.shields.io/github/license/Gary9033/ytcommentcrawler)
![Repo Size](https://img.shields.io/github/repo-size/Gary9033/ytcommentcrawler)
![Stars](https://img.shields.io/github/stars/Gary9033/ytcommentcrawler?style=social)

> YouTube 留言抓取、文字雲分析與 AI 語音轉錄的一站式工具。

## 操作展示

https://github.com/user-attachments/assets/18608c94-85e2-474b-8038-e89e1ade1eac

## 🛠 功能特色
* **影片／音訊下載：** 貼上單一影片網址，可下載 MP4（最佳畫質、1080p、720p、480p）或 MP3（最高品質、320、192、128 kbps）。下載與轉檔使用 yt-dlp + FFmpeg，不需要 API Key；MP3 碼率不會提高來源本身的音質。
* **字幕下載：** 在「字幕下載」分頁貼上單一影片網址，讀取清單後選擇人工／自動 CC、語言，按「準備字幕檔」再下載 SRT 或 TXT。只顯示人工上傳或原始語音的字幕，排除 YouTube 即時翻譯字幕。使用 yt-dlp 取得平台現有字幕，格式轉換需要 FFmpeg；無字幕時可改用語音轉錄。支援範圍取決於平台及影片，不包含畫面內燒錄的文字。需登入時可設定 `YTDLP_COOKIE_FILE` 或 `YTDLP_COOKIES_FROM_BROWSER`（例如 `edge`），僅在明確設定後讀取 Cookies。
  - YouTube 回傳 HTTP 429 時會自動短暫重試。若仍失敗，請稍候 10～30 分鐘，或設定 Cookies 後再試；即時翻譯的自動字幕較容易被限制。
* **留言抓取：** 自動抓取指定影片的所有留言（包含頂層與回覆）。
* **視覺化分析：** 生成高解析度文字雲（Word Cloud）與 Top 20 高頻詞分析柱狀圖。
* **AI 語音轉錄：** 使用 **Faster-Whisper (large-v3-turbo)** 將影片音訊轉換為文字，支援 99 種語言。
  - 🎯 實時語言檢測與準確度顯示
  - 🧹 自動清理臨時音訊檔案
  - ⚡ 批次辨識（預設 4）、跨頁面重跑快取模型，直接解碼下載音訊以省去 WAV 轉檔
  - ⏱️ 顯示辨識進度與下載／轉錄／總耗時；可指定語言以略過自動偵測
  - 📄 優先使用選定的原始平台 CC，直接提供 SRT、TXT，不下載音訊或執行 Whisper；沒有 CC 時才進行語音辨識
* **匯出功能：** 支援留言匯出為 CSV，轉錄結果匯出為 TXT，文字雲下載為 PNG。

## 🚀 從零開始：快速安裝與執行

### Docker 啟動（不需要在電腦安裝 Python 或 FFmpeg）

安裝並啟動 Docker Desktop（Windows 請使用 WSL 2 與 Linux containers），在專案目錄執行：

```bash
docker compose up -d --build
```

開啟 http://localhost:8502 。預設使用 CPU 轉錄，速度較慢；容器已包含 FFmpeg、Deno、中文字型與瀏覽器模擬依賴。
第一次語音辨識會下載 large-v3-turbo 模型，需要網路及額外磁碟空間；模型保存在 `model-cache` volume，重建容器不需重新下載。

如需抓留言，先將 `.env.example` 複製為 `.env` 並填入 `YOUTUBE_API_KEY`；字幕、轉錄與影片下載不需要這個金鑰。
`.env` 不會被放進映像檔，Compose 只將指定的金鑰傳入容器。

使用 NVIDIA GPU 時，主機須有相容的 NVIDIA 驅動及容器 GPU 支援（Linux 需 NVIDIA Container Toolkit；Windows 需 Docker Desktop 的 WSL 2 GPU 支援）：

```bash
docker compose -f compose.yaml -f compose.gpu.yaml up -d --build
```

GPU 映像另含 CUDA 12 cuBLAS 與 cuDNN 9。若 GPU 模式無法啟動，請先確認主機的 GPU 容器環境。

```bash
# 查看執行紀錄
docker compose logs -f toolbox
# 停止容器，保留模型快取
docker compose down
# 更新 yt-dlp 等依賴後重新建置
docker compose build --pull --no-cache
docker compose up -d
```

GPU 版管理指令也須加上 `-f compose.yaml -f compose.gpu.yaml`。
容器無法直接讀取 Windows 瀏覽器 Cookies；需要登入時，請將匯出的 Cookies 檔掛載到容器內可寫入的獨立路徑，並設定 `YTDLP_COOKIE_FILE` 為容器內路徑。
下載的結果仍由網頁按鈕存到你的電腦。連接埠預設只供本機存取。

以下為不使用 Docker 的安裝方式。

### 1. 複製專案 (Git Clone)
開啟您的終端機（Terminal / PowerShell / Anaconda Prompt），執行：
```bash
git clone https://github.com/Gary9033/ytcommentcrawler.git
cd ytcommentcrawler
```

### 2. 使用 Conda 建立環境
建議建立獨立環境以避免套件衝突：
```bash
# 建立並進入 Conda 環境
conda create -n yt_monster python=3.11 -y
conda activate yt_monster

# 安裝音訊處理必備工具 (FFmpeg)
# 語音轉錄與音訊下載功能必須安裝此工具
conda install -c conda-forge ffmpeg -y

# 安裝專案所需的 Python 套件
pip install -r requirements.txt
```

### 3. 啟動程式 (Run)
啟動 Streamlit 網頁介面：
```bash
streamlit run youtube_toolbox.py
```
*啟動後，瀏覽器通常會自動開啟 `http://localhost:8501`。*

---

## 📂 檔案結構說明
- `youtube_toolbox.py`：**合併版主程式（最推薦使用）**，包含留言分析、語音轉錄、CC 字幕與影片／音訊下載。
- `requirements.txt`：所有 Python 套件的依賴清單。
- `doc/`：存放專案展示圖片與 Logo。
- `GEMINI.md`：提供給 AI 助手的專案開發上下文文件。

## ⚠️ 重要提醒
- **YouTube API Key：** 將 `.env.example` 複製為 `.env`，填入 `YOUTUBE_API_KEY=你的金鑰` 後再啟動 Streamlit。`.env` 已被 Git 忽略，請勿強制提交；GitHub 只保存不含金鑰的範例檔。若金鑰曾提交至公開版本庫，請至 Google Cloud Console 撤銷並重新建立。
- **GPU 加速：** 本機語音轉錄預設使用 NVIDIA GPU（cuda／float16）；可透過環境變數 `WHISPER_DEVICE=cpu`、`WHISPER_COMPUTE_TYPE=int8` 改用 CPU，無須修改程式。Docker 預設為 CPU，GPU 版使用前述 Compose 指令。批次大小預設為 4，記憶體不足會逐次減半，最後退回逐段辨識（1）；重試會從頭開始。
- **轉錄範圍：** 目前會轉錄整部影片，YouTube 網址的 `t=` 播放起點不會裁切音訊。
- **中文字型：** 本機預設使用 Windows 的 `msjh.ttc`；Linux 或 macOS 可設定 `FONT_PATH` 環境變數指定中文字型。Docker 已設定 Noto CJK 字型。
- **臨時檔案：** 直接下載 WebM／M4A 等原始音訊，每次使用獨立的臨時檔名，轉錄後自動刪除。

📜 本專案採用 MIT License 授權。
