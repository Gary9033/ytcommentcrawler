# YouTube 怪獸 (YouTube Monster) 🚀
![License](https://img.shields.io/github/license/Gary9033/ytcommentcrawler)
![Repo Size](https://img.shields.io/github/repo-size/Gary9033/ytcommentcrawler)
![Stars](https://img.shields.io/github/stars/Gary9033/ytcommentcrawler?style=social)

> YouTube 留言抓取、文字雲分析與 AI 語音轉錄的一站式工具。

## 🛠 功能特色
* **留言抓取：** 自動抓取指定影片的所有留言（包含頂層與回覆）。
* **視覺化分析：** 生成高解析度文字雲（Word Cloud）與 Top 20 高頻詞分析柱狀圖。
* **AI 語音轉錄：** 使用 **Faster-Whisper (large-v3-turbo)** 將影片音訊轉換為文字，支援 99 種語言。
* **匯出功能：** 支援留言匯出為 CSV，轉錄結果匯出為 TXT，文字雲下載為 PNG。

## 🚀 快速上手
1. **安裝需求：**
   請確保已安裝 **Python 3.10+** 並具備 **FFmpeg**（用於音訊處理）。
   ```bash
   pip install -r requirements.txt
   ```
2. **執行工具箱（推薦）：**
   包含所有功能（留言抓取 + 語音轉錄）：
   ```bash
   streamlit run youtube_toolbox.py
   ```
3. **執行獨立爬蟲：**
   僅執行留言抓取功能：
   ```bash
   streamlit run cloud.py
   ```

## 📂 檔案結構
- `youtube_toolbox.py`：合併版主程式，提供 Tab 切換功能。
- `cloud.py`：原版留言抓取程式。
- `doc/`：存放專案展示圖片。
- `requirements.txt`：列出所有必要的 Python 套件。
- `GEMINI.md`：AI 助手專用的專案說明文件。

## ⚠️ 注意事項
- **API Key：** 本工具需要 YouTube Data API v3 金鑰。
- **字型設定：** 預設使用 Windows 微軟正黑體 (`C:/Windows/Fonts/msjh.ttc`)。
- **硬體需求：** 語音轉錄預設使用 CUDA 加速（GPU），若無 GPU 請修改 `youtube_toolbox.py` 中的設備設定。

📜 本專案採用 MIT License 授權。
