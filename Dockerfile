FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 YOLO_CONFIG_DIR=/tmp/ultralytics MPLCONFIGDIR=/tmp/matplotlib OMP_NUM_THREADS=2
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# CPU wheels keep the default image usable without NVIDIA; GPU has a separate override.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN --mount=type=bind,source=wheelhouse,target=/wheelhouse \
    if [ "$TORCH_INDEX" = "https://download.pytorch.org/whl/cpu" ] && ls /wheelhouse/torch-*.whl >/dev/null 2>&1; then \
      pip install --no-cache-dir --no-index --find-links=/wheelhouse -r requirements.txt; \
    else \
      pip install --no-cache-dir --timeout 120 torch==2.8.0 torchvision==0.23.0 --index-url ${TORCH_INDEX} && \
      pip install --no-cache-dir --timeout 120 -r requirements.txt; \
    fi
COPY backend ./backend
COPY ml ./ml
COPY worker ./worker
COPY scripts ./scripts
COPY models/yolo11n.pt /models/yolo11n.pt
RUN mkdir -p /data
ENV STORAGE_PATH=/data MODEL_PATH=/models/yolo11n.pt
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
