"""Bounded producer/consumer decode pipeline; tracker order is never shuffled."""
from queue import Empty, Full, Queue
from threading import Event, Thread


class PrefetchFrames:
    def __init__(self, container, stream, capacity=4):
        self.container, self.stream = container, stream
        self.queue = Queue(maxsize=capacity)
        self.stop = Event()
        self.thread = Thread(target=self._produce, name="video-decode", daemon=True)

    def _put(self, value):
        while not self.stop.is_set():
            try:
                self.queue.put(value, timeout=0.1)
                return
            except Full:
                pass

    def _produce(self):
        try:
            for frame in self.container.decode(self.stream):
                if self.stop.is_set():
                    break
                self._put((frame, None))
        except Exception as exc:
            self._put((None, exc))
        finally:
            self.container.close()
            self._put((None, None))

    def __enter__(self):
        self.thread.start()
        return self

    def __iter__(self):
        while True:
            try:
                frame, error = self.queue.get(timeout=0.2)
            except Empty:
                if not self.thread.is_alive():
                    raise RuntimeError("Декодер завершился без результата")
                continue
            if error is not None:
                raise error
            if frame is None:
                return
            yield frame

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("Декодер не завершился за 5 секунд")
