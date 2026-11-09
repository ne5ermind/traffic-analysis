"""Fetch official YOLO weights for the single-model or ensemble pipeline."""
import argparse
import ssl
from pathlib import Path
from urllib.request import urlopen

MODEL_DIR = Path(__file__).resolve().parents[1] / "data" / "models"
RELEASE = "https://github.com/ultralytics/assets/releases/download/v8.3.0"
SUPPORTED = ("yolo11n.pt", "yolo11s.pt", "yolo11m.pt", "yolov10m.pt", "yolov8m.pt")
MIN_SIZE = {"yolo11n.pt": 4_000_000, "yolo11s.pt": 15_000_000}


def fetch(name):
    destination = MODEL_DIR / name
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    minimum = MIN_SIZE.get(name, 20_000_000)
    if destination.exists() and destination.stat().st_size > minimum:
        print(f"Вес уже есть: {destination}")
        return
    temporary = destination.with_suffix(".download")
    try:
        try:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            context = ssl.create_default_context()
        with urlopen(f"{RELEASE}/{name}", timeout=120, context=context) as source, temporary.open("wb") as output:
            while block := source.read(1024 * 1024):
                output.write(block)
        if temporary.stat().st_size < minimum:
            raise RuntimeError(f"Слишком маленький файл весов: {name}")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    print(f"Сохранено: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ensemble", action="store_true", help="Выбранная модель (по умолчанию YOLO11m) + YOLOv10m")
    parser.add_argument("--model", choices=SUPPORTED, help="Скачать модель или выбрать первую модель ансамбля")
    options = parser.parse_args()
    primary = options.model or "yolo11m.pt"
    if options.ensemble and primary == "yolov10m.pt":
        parser.error("Первая модель ансамбля должна отличаться от YOLOv10m")
    names = (primary, "yolov10m.pt") if options.ensemble else (primary,)
    for name in names:
        fetch(name)


if __name__ == "__main__":
    main()
