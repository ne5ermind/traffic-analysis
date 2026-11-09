"""Sample frames by presentation timestamp, without decoding them to NumPy first."""
from math import floor, isfinite


def budgeted_fps(current_fps: float, video_seconds: float, wall_seconds: float) -> float:
    """Reduce (never raise) inference frequency when the two-times-real-time budget is at risk."""
    if not all(isfinite(value) for value in (current_fps, video_seconds, wall_seconds)):
        raise ValueError("Параметры оценки скорости должны быть конечными")
    if current_fps <= 0:
        raise ValueError("Частота кадров должна быть положительной")
    if video_seconds <= 0 or wall_seconds <= 0:
        return current_fps
    # Leave 25% for decoding variability and more crowded sections of the clip.
    feasible = current_fps * 1.5 * video_seconds / wall_seconds
    return min(current_fps, max(2.0, floor(feasible * 2) / 2))


class FrameSampler:
    def __init__(self, target_fps: float):
        if not 0 < target_fps <= 60:
            raise ValueError("Частота кадров должна быть в диапазоне (0, 60]")
        self.period = 1 / target_fps
        self.next_time = None
        self.last_time = None
        self.last_input_time = None

    def set_rate(self, target_fps: float):
        if not 0 < target_fps <= 60:
            raise ValueError("Частота кадров должна быть в диапазоне (0, 60]")
        self.period = 1 / target_fps
        self.next_time = self.last_time + self.period if self.last_time is not None else None

    def accept(self, time_s: float) -> bool:
        if not isfinite(time_s):
            raise ValueError("Время кадра должно быть конечным")
        # A few containers reset PTS at a discontinuity.  Restarting the phase
        # avoids rejecting the remainder of an otherwise decodable video.
        if self.last_input_time is not None and time_s + 1e-4 < self.last_input_time:
            self.next_time = time_s + self.period
            self.last_time = time_s
            self.last_input_time = time_s
            return True
        self.last_input_time = time_s
        if self.next_time is None:
            self.next_time = time_s + self.period
            self.last_time = time_s
            return True
        if time_s + 1e-4 < self.next_time:
            return False
        skipped_periods = floor((time_s + 1e-4 - self.next_time) / self.period) + 1
        self.next_time += skipped_periods * self.period
        self.last_time = time_s
        return True
