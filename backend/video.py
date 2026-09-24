import json
import subprocess
from fractions import Fraction
import cv2


def inspect_video(path, preview):
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
        data = json.loads(probe.stdout)
        s = data["streams"][0]
        fps = float(Fraction(s.get("avg_frame_rate", "0/1")))
        duration = float(s.get("duration") or data["format"].get("duration") or 0)
        if not 0 < fps <= 1000 or duration <= 0:
            raise ValueError("Некорректная длительность или частота кадров")
        cap = cv2.VideoCapture(str(path))
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise ValueError("Не удалось декодировать первый кадр")
        if not cv2.imwrite(str(preview), frame):
            raise OSError("Не удалось сохранить превью: проверьте свободное место")
        brightness, sharpness = [], []
        for t in (0, duration * 0.25, duration * 0.5, duration * 0.75):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, sample = cap.read()
            if ok:
                gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
                brightness.append(float(gray.mean()))
                sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        cap.release()
        warnings = []
        if min(frame.shape[:2]) < 480:
            warnings.append("Низкое разрешение записи")
        if fps < 10:
            warnings.append("Низкая частота кадров: быстрые объекты могут теряться")
        if brightness and min(brightness) < 40:
            warnings.append("На записи есть тёмные участки")
        if sharpness and min(sharpness) < 35:
            warnings.append("Возможна размытость изображения")
        return dict(
            width=frame.shape[1],
            height=frame.shape[0],
            fps=fps,
            duration=duration,
            codec=s.get("codec_name", "unknown"),
            frame_count=int(s["nb_frames"]) if str(s.get("nb_frames", "")).isdigit() else round(duration * fps),
            container=data.get("format", {}).get("format_name", "unknown"),
            file_size=path.stat().st_size,
            warnings=warnings,
            brightness=brightness,
            sharpness=sharpness,
        )
    except (subprocess.SubprocessError, KeyError, IndexError, ZeroDivisionError, json.JSONDecodeError) as e:
        raise ValueError("Видео повреждено или кодек не поддерживается") from e
