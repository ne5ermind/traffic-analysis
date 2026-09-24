import os
from pathlib import Path

STORAGE_PATH = Path(os.getenv("STORAGE_PATH", "./data")).resolve()
STORAGE_PATH.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{STORAGE_PATH / 'traffic.db'}")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_GB", "30")) * 1024**3)
ACTIVE = ("queued", "processing")
