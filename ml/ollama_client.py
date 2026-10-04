"""Isolated HTTP transport: killing this process cancels the Ollama request."""
import json
import sys
import urllib.request


def run():
    config = json.load(sys.stdin)
    url, payload = config["url"].rstrip("/"), config["payload"]
    with urllib.request.urlopen(url + "/api/tags", timeout=10) as response:
        models = json.load(response)["models"]
    selected = next((m for m in models if m.get("name") == payload["model"]), None)
    if not selected or selected.get("remote_model") or selected.get("remote_host"):
        raise ValueError("Нужна скачанная локальная модель: " + payload["model"])
    req = urllib.request.Request(url + "/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=config["timeout"]) as response:
        return json.load(response)


if __name__ == "__main__":
    try:
        result = run()
    except Exception as exc:
        result = {"error": str(exc)}
    json.dump(result, sys.stdout)
