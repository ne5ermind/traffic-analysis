import pytest
from app.vision.frames import PrefetchFrames


class Container:
    closed=False
    def __init__(self, fail=False): self.fail=fail
    def decode(self, stream):
        for value in range(20):
            if self.fail and value==3: raise ValueError('decode failure')
            yield value
    def close(self): self.closed=True


def test_order_cleanup_on_success_cancel_and_decode_error():
    source=Container()
    with PrefetchFrames(source,None,2) as frames: assert list(frames)==list(range(20))
    assert source.closed and not frames.thread.is_alive()
    source=Container()
    with PrefetchFrames(source,None,1) as frames:
        for value in frames: break
    assert source.closed and not frames.thread.is_alive()
    source=Container(True)
    with pytest.raises(ValueError,match='decode failure'):
        with PrefetchFrames(source,None,1) as frames: list(frames)
    assert source.closed
