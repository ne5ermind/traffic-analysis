"""Load official weights, with a portable FP16→FP32 route for sealed CPUs."""
from pathlib import Path


def load_yolo(weights: str | Path):
    from ultralytics import YOLO
    from .storage import ROOT
    weights = Path(weights)
    try:
        return YOLO(str(weights))
    except RuntimeError as exc:
        if "cpuinfo" not in str(exc).lower():
            raise
    # Some restricted Linux runtimes hide /proc/cpuinfo. PyTorch cannot convert
    # FP16 tensors with its native kernel there. NumPy performs that conversion.
    import numpy as np
    import torch

    torch.backends.mkldnn.enabled = False
    if hasattr(torch.backends, "nnpack"):
        torch.backends.nnpack.set_flags(False)
    cache = ROOT / "model-cache" / (weights.stem + "-fp32-v2.pt")
    if not cache.exists() or cache.stat().st_mtime < weights.stat().st_mtime:
        cache.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = torch.load(str(weights), map_location="cpu", weights_only=False)
        network = checkpoint.get("ema") or checkpoint["model"]
        for module in network.modules():
            for name, parameter in tuple(module._parameters.items()):
                if parameter is not None and parameter.dtype == torch.float16:
                    tensor = torch.from_numpy(parameter.detach().numpy().astype(np.float32))
                    module._parameters[name] = torch.nn.Parameter(tensor, requires_grad=parameter.requires_grad)
            for name, buffer in tuple(module._buffers.items()):
                if buffer is not None and buffer.dtype == torch.float16:
                    module._buffers[name] = torch.from_numpy(buffer.detach().numpy().astype(np.float32))
            # Ultralytics Detect also keeps stride/anchors as plain tensor attrs.
            for name, value in tuple(vars(module).items()):
                if isinstance(value, torch.Tensor) and value.dtype == torch.float16:
                    setattr(module, name, torch.from_numpy(value.detach().numpy().astype(np.float32)))
        checkpoint["model"] = network
        checkpoint["ema"] = network
        temporary = cache.with_suffix(".tmp")
        torch.save(checkpoint, temporary)
        temporary.replace(cache)
    return YOLO(str(cache))
