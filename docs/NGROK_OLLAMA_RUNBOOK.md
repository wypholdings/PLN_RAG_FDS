# Ngrok + Ollama (SageMaker)

Este documento queda como alternativa de despliegue. La version final validada usa Ollama local en `http://127.0.0.1:11434` y no depende de ngrok.

## 1) Prerrequisitos en SageMaker

- Ollama corriendo en `127.0.0.1:11434`.
- Modelo descargado, por ejemplo:

```bash
docker exec ollama ollama pull qwen2.5:7b-instruct
docker exec ollama ollama list
```

- Token de ngrok disponible como variable de entorno:

```bash
export NGROK_AUTHTOKEN="<tu_token_ngrok>"
```

## 2) Script de endpoint ngrok

```bash
python scripts/setup_ngrok_ollama.py
```

El script:

- valida que Ollama responda en local,
- abre túnel ngrok al puerto `11434`,
- guarda el endpoint en:
  - `data/runtime/ollama_endpoint.json`

## 3) Usar endpoint en este repo

```bash
export OLLAMA_BASE_URL="$(python - <<'PY'
import json
print(json.load(open('data/runtime/ollama_endpoint.json'))['ollama_base_url'])
PY
)"
```

## 4) Verificación

```bash
curl -s "$OLLAMA_BASE_URL/api/tags"
```

Si devuelve JSON con modelos, la conexión quedó lista para Fase 5.
