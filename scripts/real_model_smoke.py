"""Explicit real-model validation; does not create fake traffic or claim accuracy."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.video import inspect_video
from ml.pipeline import run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", choices=("fast", "balanced", "accurate"), default="balanced")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        root = args.output or Path(temporary)
        root.mkdir(parents=True, exist_ok=True)
        metadata = inspect_video(args.video, root / "preview.jpg")
        result = run_pipeline(
            args.video,
            root / "tracks.sqlite",
            metadata,
            {"zones": [], "lines": []},
            profile=args.profile,
            report=lambda **p: print(json.dumps(p, ensure_ascii=False)),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
