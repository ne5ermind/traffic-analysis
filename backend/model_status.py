import json
import time
import urllib.request
from ml.local_vlm import LOCAL_VLM_ENABLED, LOCAL_VLM_URL, LOCAL_VLM_MODEL, LOCAL_VLM_SCENE_MODEL

_cache = (0, {})


def model_status():
    global _cache
    now = time.monotonic()
    if now - _cache[0] < 15:
        return _cache[1]
    names = [LOCAL_VLM_SCENE_MODEL, LOCAL_VLM_MODEL]
    result = {"enabled": LOCAL_VLM_ENABLED, "ready": False, "models": names}
    if LOCAL_VLM_ENABLED:
        try:
            with urllib.request.urlopen(LOCAL_VLM_URL.rstrip('/') + '/api/tags', timeout=2) as response:
                models = json.load(response)["models"]
            present = {m["name"] for m in models if not m.get("remote_model") and not m.get("remote_host")}
            result.update(ready=all(n in present for n in names), missing=[n for n in names if n not in present])
        except (OSError, ValueError, KeyError):
            result["message"] = "Ollama недоступна. Запустите Ollama на Mac."
    _cache = now, result
    return result
