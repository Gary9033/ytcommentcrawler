# YouTube 怪獸 (YouTube Monster) 🚀
![License](https://img.shields.io/github/license/Gary9033/ytcommentcrawler)
![Repo Size](https://img.shields.io/github/repo-size/Gary9033/ytcommentcrawler)
![Stars](https://img.shields.io/github/stars/Gary9033/ytcommentcrawler?style=social)
https://desktop-l8029ug.tail4cc5a3.ts.net/
> YouTube 留言抓取、文字雲分析與 AI 語音轉錄的一站式工具。

## 🛠 功能特色
* **留言抓取：** 自動抓取指定影片的所有留言（包含頂層與回覆）。
* **視覺化分析：** 生成高解析度文字雲（Word Cloud）與 Top 20 高頻詞分析柱狀圖。
* **AI 語音轉錄：** 使用 **Faster-Whisper (large-v3-turbo)** 將影片音訊轉換為文字，支援 99 種語言。
  - 🎯 實時語言檢測與準確度顯示
  - 🧹 自動清理臨時音訊檔案
  - ⚡ 批次辨識（預設 4）、跨頁面重跑快取模型，直接解碼下載音訊以省去 WAV 轉檔
  - ⏱️ 顯示辨識進度與下載／轉錄／總耗時；可指定語言以略過自動偵測
* **匯出功能：** 支援留言匯出為 CSV，轉錄結果匯出為 TXT，文字雲下載為 PNG。

## 🚀 從零開始：快速安裝與執行

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
- `youtube_toolbox.py`：**合併版主程式（最推薦使用）**，包含「留言分析」與「語音轉錄」兩個分頁。
- `requirements.txt`：所有 Python 套件的依賴清單。
- `doc/`：存放專案展示圖片與 Logo。
- `GEMINI.md`：提供給 AI 助手的專案開發上下文文件。

## ⚠️ 重要提醒
- **YouTube API Key：** 程式內目前已預填一組 API 金鑰，若因流量限制失效，請至 Google Cloud Console 申請並更換程式碼中的 `API_KEY`。
- **GPU 加速：** 語音轉錄預設在 `modules/transcription.py` 使用 `device="cuda"`、`compute_type="float16"` (NVIDIA GPU)。批次大小預設為 4，記憶體不足會逐次減半，最後退回原本逐段辨識（1）；重試會從頭開始。批次模式可能改變分段與辨識結果，可選 1 比較。沒有 NVIDIA 顯卡時，需將模型設定改為 `device="cpu"`、`compute_type="int8"`。
- **轉錄範圍：** 目前會轉錄整部影片，YouTube 網址的 `t=` 播放起點不會裁切音訊。
- **中文字型：** 預設路徑為 Windows 的 `msjh.ttc`（微軟正黑體）。若在 Linux 或 macOS 上執行，請修改 `FONT_PATH`。
- **臨時檔案：** 直接下載 WebM／M4A 等原始音訊，每次使用獨立的臨時檔名，轉錄後自動刪除。

📜 本專案採用 MIT License 授權。
