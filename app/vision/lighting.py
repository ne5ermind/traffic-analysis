"""Conservative luminance enhancement; no synthetic night-quality claims."""
import cv2
import numpy as np


class LowLightProcessor:
    def __init__(self, mode="auto"):
        if mode not in ("day", "night", "auto"):
            raise ValueError("Неизвестный режим освещения")
        self.mode = mode
        self.dark = mode == "night"
        self.brightness = None
        self.enhanced_frames = 0
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.gamma = np.round(255 * (np.arange(256) / 255) ** 0.7).astype(np.uint8)

    def process(self, frame):
        if self.mode == "day":
            return frame, False
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        level = float(np.median(lab[::8, ::8, 0])) / 255
        self.brightness = level if self.brightness is None else 0.9 * self.brightness + 0.1 * level
        if self.mode == "auto":
            # Hysteresis avoids switching models on each passing headlight.
            if self.brightness < 0.22:
                self.dark = True
            elif self.brightness > 0.32:
                self.dark = False
        if not self.dark:
            return frame, False
        luminance = cv2.LUT(lab[:, :, 0], self.gamma)
        lab[:, :, 0] = cv2.addWeighted(luminance, 0.65, self.clahe.apply(luminance), 0.35, 0)
        self.enhanced_frames += 1
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), True
