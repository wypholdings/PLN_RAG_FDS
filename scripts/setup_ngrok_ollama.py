from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from pyngrok import ngrok


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "data" / "runtime"
OUT_FILE = OUT_DIR / "ollama_endpoint.json"


def wait_ollama(base_url: str, timeout_seconds: int = 60) -> None:
    started = time.time()
    last_error = ""
    while time.time() - started < timeout_seconds:
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                return
            last_error = f"status_code={response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Ollama no responde en {base_url}: {last_error}")


def main() -> int:
    ngrok_token = os.environ.get("NGROK_AUTHTOKEN", "").strip()
    if not ngrok_token:
        raise SystemExit("Falta NGROK_AUTHTOKEN en variables de entorno.")

    ollama_local = os.environ.get("OLLAMA_LOCAL_URL", "http://127.0.0.1:11434").rstrip("/")
    wait_ollama(ollama_local)

    ngrok.set_auth_token(ngrok_token)
    tunnel = ngrok.connect(addr=11434, proto="http")
    public_url = tunnel.public_url.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "ollama_local_url": ollama_local,
        "ollama_ngrok_url": public_url,
        "ollama_base_url": public_url,
        "created_at_epoch": int(time.time()),
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

