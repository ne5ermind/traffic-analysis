from types import SimpleNamespace
import numpy as np


TRACKER_PROFILES = {
    "fast": dict(track_high_thresh=0.25, track_low_thresh=0.08, new_track_thresh=0.30, track_buffer=60, match_thresh=0.80),
    "balanced": dict(track_high_thresh=0.22, track_low_thresh=0.06, new_track_thresh=0.24, track_buffer=90, match_thresh=0.85),
    "accurate": dict(track_high_thresh=0.18, track_low_thresh=0.05, new_track_thresh=0.20, track_buffer=90, match_thresh=0.90),
}


class ByteTracker:
    def __init__(self, fps, profile="balanced"):
        from ultralytics.trackers.byte_tracker import BYTETracker

        options = TRACKER_PROFILES[profile]
        self.tracker = BYTETracker(
            SimpleNamespace(**options, fuse_score=True),
            frame_rate=max(1, round(fps)),
        )
        # Convert the tracker's frame budget using the actual sampled FPS.
        # At very low FPS the minimum buffer spans more than two seconds.
        self.buffer_seconds = (self.tracker.max_time_lost + 1) / max(0.001, fps)

    def update(self, detections, shape):
        from ultralytics.engine.results import Boxes

        data = np.array([[*d.bbox, d.confidence, d.class_id] for d in detections], dtype=np.float32).reshape(-1, 6)
        tracks = self.tracker.update(Boxes(data, orig_shape=shape))
        # Removed tracks otherwise accumulate over very long recordings.
        self.tracker.removed_stracks = self.tracker.removed_stracks[-1000:]
        return [dict(bbox=list(map(float, t[:4])), track_id=int(t[4]), confidence=float(t[5]), class_id=int(t[6])) for t in tracks]
