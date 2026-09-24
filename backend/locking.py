from contextlib import contextmanager
import fcntl
from backend.config import STORAGE_PATH


@contextmanager
def project_lock(project_id, blocking=False):
    locks = STORAGE_PATH / ".locks"
    locks.mkdir(exist_ok=True)
    with (locks / f"{project_id}.lock").open("a") as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as e:
            raise ValueError("Проект занят. Дождитесь остановки обработки и повторите.") from e
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
