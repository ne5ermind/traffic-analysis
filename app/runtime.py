"""One CPU budget shared by decoding, preprocessing and inference."""
import os


def runtime_settings():
    return {"cpu_budget": 4, "inference_threads": 2, "decode_threads": 1,
            "prefetch_frames": 4, "device": os.getenv("INNOVA_DEVICE", "cpu")}


def configure_runtime():
    settings = runtime_settings()
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = str(settings["inference_threads"])
    import torch
    import cv2
    torch.set_num_threads(settings["inference_threads"])
    cv2.setNumThreads(1)
    return settings
