import sys
from redis import Redis
from rq import Queue, Worker, SimpleWorker
from backend.config import REDIS_URL
from backend.db import init_db

init_db()
connection = Redis.from_url(REDIS_URL)
# Avoid unsafe fork after native CV runtime initialization on macOS.
worker_class = SimpleWorker if sys.platform == "darwin" else Worker
worker_class([Queue("analysis", connection=connection)], connection=connection).work()
