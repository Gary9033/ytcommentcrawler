# GEMINI.md - YouTube Comment Crawler (ytcommentcrawler)

This project, also known as **YouTube 怪獸 (YouTube Monster)**, is a comprehensive tool for analyzing YouTube videos through comment scraping and audio transcription.

## Project Overview
- **Purpose:** Automated scraping of YouTube comments, visualization via word clouds and frequency charts, and AI-powered audio-to-text transcription.
- **Frontend:** Built with **Streamlit** for a responsive web-based terminal interface.
- **Core Technologies:**
  - **YouTube Data API v3:** For fetching comment threads and replies.
  - **Pandas:** For data manipulation and export to CSV.
  - **WordCloud & Matplotlib:** For generating high-resolution visual summaries.
  - **jieba:** For Chinese text segmentation and NLP analysis.
  - **Faster-Whisper:** For high-speed, high-accuracy audio transcription (supporting 99 languages).
  - **yt-dlp:** For efficient audio extraction from YouTube URLs.

## Architecture & Key Files
- `cloud.py`: The original entry point focusing on comment scraping, word cloud generation, and Top 20 frequency analysis.
- `youtube_toolbox.py`: The "Merged Edition" featuring a tabbed interface that combines the comment crawler with the Whisper transcription engine.
- `requirements.txt`: Lists all Python dependencies (Streamlit, Google API client, Faster-Whisper, etc.).
- `doc/`: Contains gallery images and assets for the documentation.

## Building and Running

### Prerequisites
- **Python:** 3.10 or higher.
- **FFmpeg:** Required for audio processing (Whisper/yt-dlp).
- **GPU (Optional):** Faster-Whisper is configured to use CUDA (`float16`) in `youtube_toolbox.py`. If running on CPU, change `device="cuda"` to `device="cpu"` and `compute_type="float16"` to `compute_type="int8"`.
- **Font:** The project defaults to the Windows font `msjh.ttc` (Microsoft JhengHei). Update `FONT_PATH` in the script if running on macOS/Linux.

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
To run the full-featured toolbox:
```bash
streamlit run youtube_toolbox.py
```
To run only the comment crawler:
```bash
streamlit run cloud.py
```

## Development Conventions
- **API Keys:** The project currently uses a hardcoded YouTube API Key. For production or personal use, it is recommended to move this to an environment variable or a secrets manager.
- **Hardcoded Paths:** `FONT_PATH` is currently hardcoded for Windows.
- **Error Handling:** Basic try-except blocks are used for API calls and file operations, with errors displayed directly in the Streamlit UI.
- **Performance:** Audio transcription uses the `large-v3-turbo` model with VAD (Voice Activity Detection) filters for optimal speed and silence handling.

## Known Limitations / TODO
- [ ] Implement dynamic font path detection for cross-platform compatibility.
- [ ] Move hardcoded API keys to a `.env` file or Streamlit secrets.
- [ ] Add support for local file uploads (CSV/Audio) for analysis without a direct YouTube link.
