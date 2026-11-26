FROM denoland/deno:bin AS deno

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg \
    HF_HOME=/home/app/.cache/huggingface \
    FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-noto-cjk libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=deno /deno /usr/local/bin/deno
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt 'curl-cffi>=0.7'
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /home/app/.cache/huggingface \
    && chown -R app:app /home/app
COPY --chown=app:app youtube_toolbox.py ./
COPY --chown=app:app modules/ ./modules/
COPY --chown=app:app styles/ ./styles/
USER app
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"
CMD ["streamlit", "run", "youtube_toolbox.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]

FROM runtime AS gpu
USER root
RUN pip install 'nvidia-cublas-cu12>=12,<13' 'nvidia-cudnn-cu12>=9,<10'
ENV WHISPER_DEVICE=cuda \
    WHISPER_COMPUTE_TYPE=float16 \
    LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib
USER app

FROM runtime AS cpu
