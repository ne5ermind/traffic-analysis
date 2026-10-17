"""Geometry and passage state independent from inference and HTTP layers."""
from collections import Counter
from dataclasses import dataclass, field
from math import hypot, isfinite


def side(point, line):
    (ax, ay), (bx, by) = line
    return (bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax)


def segment_crossing(previous, current, line, epsilon=0.002):
    """Return an interpolated crossing fraction for two finite segments.

    ``epsilon`` is a perpendicular distance in normalized image coordinates,
    rather than an unscaled cross product.  Arriving exactly on a line counts;
    leaving a line on the following observation does not count a second time.
    """
    (lx, ly), (rx, ry) = line
    line_length = hypot(rx - lx, ry - ly)
    if line_length <= 0:
        return None
    a = side(previous, line) / line_length
    b = side(current, line) / line_length
    if a * b < 0:
        f = abs(a) / (abs(a) + abs(b))
    elif abs(b) <= epsilon < abs(a):
        f = 1.0
    else:
        return None
    x = previous[0] + f * (current[0] - previous[0])
    y = previous[1] + f * (current[1] - previous[1])
    dot = (x - lx) * (rx - lx) + (y - ly) * (ry - ly)
    length = (rx - lx) ** 2 + (ry - ly) ** 2
    margin = epsilon * line_length
    if dot < -margin or dot > length + margin:
        return None
    return f


def inside(point, polygon):
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    odd = False
    for p, q in zip(polygon, polygon[1:] + polygon[:1]):
        # Treat the boundary as part of the ROI.  Otherwise an anchor landing
        # exactly on the user's polygon can flicker in/out between frames.
        cross = (q[0] - p[0]) * (y - p[1]) - (q[1] - p[1]) * (x - p[0])
        if abs(cross) <= 1e-9 and (
            min(p[0], q[0]) - 1e-9 <= x <= max(p[0], q[0]) + 1e-9
            and min(p[1], q[1]) - 1e-9 <= y <= max(p[1], q[1]) + 1e-9
        ):
            return True
        if (p[1] > y) != (q[1] > y):
            xx = (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1]) + p[0]
            if x < xx:
                odd = not odd
    return odd


@dataclass
class TrackState:
    previous: tuple | None = None
    timestamp: float | None = None
    source: str | None = None
    entry_time: float | None = None
    exit_candidate: tuple | None = None
    exit_seen: int = 0
    last_passage: float = -1e9
    passed: int = 0
    seen: int = 0
    trail: list = field(default_factory=list)
    votes: Counter = field(default_factory=Counter)
    scores: dict = field(default_factory=dict)


def _record_class(votes, scores, category, confidence):
    votes[category] += 1
    score = float(confidence)
    if isfinite(score):
        total, count = scores.get(category, (0.0, 0))
        scores[category] = (total + min(1.0, max(0.0, score)), count + 1)


def _stable_class(votes, scores, fallback):
    category = votes.most_common(1)[0][0] if votes else fallback
    total, count = scores.get(category, (0.0, 0))
    return category, total / count if count else 0.0


class PassageCounter:
    """One state per tracker ID; accepts observed entry and exit line crossings.

    Frames used to confirm an exit never shift its timestamp into a later bin.
    """

    def __init__(self, entry_lines, exit_lines, roi, confirmation=2, cooldown=1.0):
        if confirmation < 1:
            raise ValueError("Подтверждение должно требовать хотя бы одно наблюдение")
        if cooldown < 0:
            raise ValueError("Пауза между проездами не может быть отрицательной")
        self.entry_lines = entry_lines
        self.exit_lines = exit_lines
        self.roi = roi
        self.confirmation = confirmation
        self.cooldown = cooldown
        self.tracks = {}

    def feed(self, identity, point, pts, category, confidence, box_size=None):
        track = self.tracks.setdefault(identity, TrackState())
        point = tuple(float(value) for value in point)
        pts = float(pts)
        if len(point) != 2 or not all(isfinite(value) for value in point) or not isfinite(pts):
            return []
        # Duplicate/out-of-order observations must not satisfy confirmation or
        # move the trajectory backwards when a source has irregular timestamps.
        if track.timestamp is not None and pts <= track.timestamp:
            return []
        track.seen += 1
        _record_class(track.votes, track.scores, category, confidence)
        track.trail.append([round(pts, 3), *point])
        track.trail = track.trail[-300:]
        produced = []
        if track.previous is not None:
            def crossings(lines):
                result = []
                for name, line in lines.items():
                    fraction = segment_crossing(track.previous, point, line)
                    if fraction is not None:
                        observed = track.timestamp + fraction * (pts - track.timestamp)
                        crossed_at = (
                            track.previous[0] + fraction * (point[0] - track.previous[0]),
                            track.previous[1] + fraction * (point[1] - track.previous[1]),
                        )
                        result.append((name, observed, crossed_at))
                return sorted(result, key=lambda item: item[1])

            entries = crossings(self.entry_lines)
            exits = crossings(self.exit_lines)
            entered_now = False
            if track.source is None and pts - track.last_passage >= self.cooldown:
                for name, observed, crossed_at in entries:
                    if (not self.roi or inside(crossed_at, self.roi)
                            or inside(point, self.roi) or inside(track.previous, self.roi)):
                        track.source, track.entry_time = name, observed
                        entered_now = True
                        break
            candidate_started = False
            if track.source and track.exit_candidate is None and pts - track.last_passage >= self.cooldown:
                eligible = [item for item in exits
                            if not entered_now or item[1] > track.entry_time + 1e-9]
                if eligible:
                    name, observed, _ = eligible[0]
                    track.exit_candidate = (name, observed)
                    track.exit_seen = 1
                    candidate_started = True
            if track.exit_candidate:
                name, observed_time = track.exit_candidate
                if not candidate_started and pts > observed_time:
                    track.exit_seen += 1
                # Confirmation occurs later, while event time remains at observed crossing.
                if track.exit_seen >= self.confirmation and pts >= observed_time:
                    stable_category, stable_confidence = _stable_class(
                        track.votes, track.scores, category)
                    produced.append({"tracker_id": identity, "category": stable_category,
                                     "confidence": stable_confidence,
                                     "from_direction": track.source,
                                     "to_direction": name, "start_s": track.entry_time,
                                     "time_s": observed_time, "trail": list(track.trail)})
                    track.source = None
                    track.entry_time = None
                    track.exit_candidate = None
                    track.exit_seen = 0
                    track.last_passage = observed_time
                    track.passed += 1
        track.previous, track.timestamp = point, pts
        return produced


class UniqueTrackCounter:
    """Count a stable, moving track once when no counting zone is drawn.

    Confirmation uses elapsed video time as well as an observation count, so a
    12 fps run is not much easier to satisfy than a 2 fps run.  The required
    motion is scaled down for genuinely small/distant boxes while retaining a
    floor above ordinary detector jitter.
    """

    def __init__(self, minimum_observations=3, minimum_duration=0.4,
                 minimum_displacement=0.005, maximum_displacement=0.02,
                 relative_displacement=0.25, minimum_mean_confidence=0.20):
        if minimum_observations < 1:
            raise ValueError("Нужно хотя бы одно наблюдение")
        if minimum_duration < 0:
            raise ValueError("Время подтверждения не может быть отрицательным")
        if not 0 <= minimum_displacement <= maximum_displacement:
            raise ValueError("Некорректный порог движения")
        if relative_displacement < 0 or not 0 <= minimum_mean_confidence <= 1:
            raise ValueError("Некорректные параметры подтверждения")
        self.minimum_observations = minimum_observations
        self.minimum_duration = minimum_duration
        self.minimum_displacement = minimum_displacement
        self.maximum_displacement = maximum_displacement
        self.relative_displacement = relative_displacement
        self.minimum_mean_confidence = minimum_mean_confidence
        self.tracks = {}

    def feed(self, identity, point, pts, category, confidence, box_size=None):
        point = tuple(float(value) for value in point)
        pts = float(pts)
        if len(point) != 2 or not all(isfinite(value) for value in point) or not isfinite(pts):
            return []
        track = self.tracks.setdefault(identity, {
            "first_s": pts, "last_s": None, "votes": Counter(), "scores": {},
            "trail": [], "counted": False, "origin": point,
            "max_displacement": 0.0, "sizes": [],
        })
        if track["last_s"] is not None and pts <= track["last_s"]:
            return []
        track["last_s"] = pts
        _record_class(track["votes"], track["scores"], category, confidence)
        displacement = hypot(point[0] - track["origin"][0], point[1] - track["origin"][1])
        track["max_displacement"] = max(track["max_displacement"], displacement)
        if box_size is not None:
            size = tuple(float(value) for value in box_size)
            if len(size) == 2 and all(isfinite(value) and value >= 0 for value in size):
                track["sizes"].append(hypot(*size))
                track["sizes"] = track["sizes"][-30:]
        track["trail"].append([round(pts, 3), *point])
        track["trail"] = track["trail"][-300:]
        observations = sum(track["votes"].values())
        if track["sizes"]:
            ordered_sizes = sorted(track["sizes"])
            characteristic_size = ordered_sizes[len(ordered_sizes) // 2]
            required_displacement = min(
                self.maximum_displacement,
                max(self.minimum_displacement,
                    characteristic_size * self.relative_displacement),
            )
        else:
            required_displacement = self.minimum_displacement
        stable_category, stable_confidence = _stable_class(
            track["votes"], track["scores"], category)
        duration = pts - track["first_s"]
        if (track["counted"] or observations < self.minimum_observations
                or duration < self.minimum_duration
                or track["max_displacement"] < required_displacement
                or stable_confidence < self.minimum_mean_confidence):
            return []
        track["counted"] = True
        return [{"tracker_id": identity, "category": stable_category,
                 "confidence": stable_confidence, "from_direction": "В кадре", "to_direction": "В кадре",
                 "start_s": track["first_s"], "time_s": pts, "trail": list(track["trail"]),
                 "motion": {"observations": observations,
                            "duration_s": round(duration, 3),
                            "displacement": round(track["max_displacement"], 5),
                            "required_displacement": round(required_displacement, 5),
                            "mean_confidence": round(stable_confidence, 4)}}]
