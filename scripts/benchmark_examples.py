"""Measure the fast pipeline on an example clip without changing user data."""
import argparse
import sys
import time
from collections import Counter
from math import hypot
from pathlib import Path

import av

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from app.ensemble import FastFrameProcessor
from app.geometry import UniqueTrackCounter
from app.sampling import FrameSampler


def benchmark(path: Path, start: float, seconds: float, target_fps: float, model="yolo11s.pt"):
    weights = PROJECT / "data/models" / model
    loading = time.monotonic()
    processor = FastFrameProcessor(weights, fps=target_fps)
    load_seconds = time.monotonic() - loading
    sampler = FrameSampler(target_fps)
    counter = UniqueTrackCounter()
    categories = {0: "pedestrian", 1: "bicycle", 2: "car", 3: "motorcycle",
                  5: "bus", 7: "truck"}
    found = Counter()
    decoded = sampled = 0
    with av.open(str(path)) as video:
        stream = video.streams.video[0]
        if start:
            video.seek(int(start / float(stream.time_base)), stream=stream, backward=True)
        beginning = end = None
        begun = time.monotonic()
        for frame in video.decode(stream):
            pts = float(frame.pts * frame.time_base)
            if pts < start:
                continue
            if pts >= start + seconds:
                break
            beginning = pts if beginning is None else beginning
            end = pts
            decoded += 1
            if not sampler.accept(pts):
                continue
            sampled += 1
            detections = processor.process_frame(frame.to_ndarray(format="bgr24"))
            for box, class_id, identity, confidence in zip(
                    detections.xyxy, detections.class_id, detections.tracker_id, detections.confidence):
                x1, y1, x2, y2 = box
                anchor = ((x1 + x2) / (2 * frame.width), y2 / frame.height)
                box_size = ((x2 - x1) / frame.width, (y2 - y1) / frame.height)
                for event in counter.feed(int(identity), anchor, pts, categories[int(class_id)],
                                          float(confidence), box_size=box_size):
                    found[event["category"]] += 1
        wall = time.monotonic() - begun
    clip = max(0, (end - beginning) if beginning is not None else 0)
    projection = load_seconds + wall * 900 / clip if clip else None
    print(f"Видео: {path.name}; модель: {model}; обработанный фрагмент: {clip:.1f} с")
    print(f"Декодировано: {decoded}, отправлено в модель: {sampled}, загрузка: {load_seconds:.1f} с, анализ: {wall:.1f} с")
    print(f"Учтённые объекты (не ручной эталон): {dict(found)}")
    if any(found.values()):
        characteristics = Counter()
        for track in counter.tracks.values():
            if not track["counted"]:
                continue
            category = track["votes"].most_common(1)[0][0]
            if category != "car":
                continue
            trail = track["trail"]
            dx = trail[-1][1] - trail[0][1]
            dy = trail[-1][2] - trail[0][2]
            duration = trail[-1][0] - trail[0][0]
            characteristics["cars_seen_3_to_5"] += 3 <= len(trail) <= 5
            characteristics["cars_seen_6_to_9"] += 6 <= len(trail) <= 9
            characteristics["cars_move_below_0_05"] += hypot(dx, dy) < .05
            characteristics["cars_move_below_0_10"] += hypot(dx, dy) < .10
            characteristics["cars_shorter_1s"] += duration < 1
        print(f"Диагностика автотреков: {dict(characteristics)}")
    if projection:
        print(f"Оценка для 15 мин на этой машине: {projection / 60:.1f} мин; "
              "это оценка скорости, а не гарантия точности или скорости в Docker")
    return projection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--start", type=float, default=120)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--fps", type=float, default=6)
    parser.add_argument("--model", choices=("yolo11s.pt", "yolo11m.pt"), default="yolo11s.pt")
    args = parser.parse_args()
    if not args.video.is_file() or args.seconds <= 0 or args.start < 0:
        parser.error("Укажите существующее видео, --seconds > 0 и --start >= 0")
    benchmark(args.video, args.start, args.seconds, args.fps, args.model)


if __name__ == "__main__":
    main()
