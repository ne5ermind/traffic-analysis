FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/innova
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Explicit CPU build avoids downloading CUDA runtime dependencies.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r requirements.txt
COPY app app
COPY static static
COPY scripts scripts
RUN mkdir -p data/models data/uploads data/runs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
