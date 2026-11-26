"""Fine-tune a local detector on a user-supplied, annotated night dataset."""
import argparse
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.model import load_yolo
from app.runtime import configure_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='Local Ultralytics dataset YAML; separate train/val/test recordings')
    parser.add_argument('--base', type=Path, default=Path('data/models/yolo11s.pt'))
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--output', type=Path, default=Path('data/models/yolo11s-night.pt'))
    args=parser.parse_args()
    if not args.data.is_file() or not args.base.is_file() or args.epochs < 1:
        parser.error('Existing local dataset/base weights and positive epochs are required')
    if args.output.exists():
        parser.error('Output already exists; choose a new filename')
    # Forbid dataset download hooks: training must only use prepared local data.
    import yaml
    config=yaml.safe_load(args.data.read_text())
    if not isinstance(config,dict) or config.get('download') or any(str(config.get(k,'')).startswith(('http:', 'https:')) for k in ('path','train','val','test')):
        parser.error('Only local datasets without a download hook are accepted')
    configure_runtime()
    model=load_yolo(args.base)
    model.train(data=str(args.data.resolve()), epochs=args.epochs, device='cpu', workers=0,
                batch=2, imgsz=640, seed=42, deterministic=True, project='artifacts/night-training',
                name='night', hsv_v=0.45, hsv_s=0.3, plots=False)
    best=Path(model.trainer.best)
    if not best.is_file(): raise RuntimeError('Training did not produce best.pt')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best,args.output)
    print(f'Saved {args.output}. Evaluate on held-out night recordings before accepting quality.')


if __name__=='__main__': main()
