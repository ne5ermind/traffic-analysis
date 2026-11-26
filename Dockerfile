FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend frontend
COPY scripts/build-frontend.mjs scripts/build-frontend.mjs
COPY tailwind.config.js ./
COPY static static
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 INNOVA_DEVICE=cpu OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
WORKDIR /srv/innova
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r requirements.txt
COPY app app
COPY static static
COPY --from=frontend /build/static/assets static/assets
COPY scripts scripts
RUN mkdir -p data/models data/uploads data/runs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
