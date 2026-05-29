# Fase 5 - Generacion con Ollama y fuentes obligatorias

## Objetivo

Responder preguntas sobre FDS usando solo fragmentos recuperados por el retriever local y forzar trazabilidad de fuentes en cada respuesta.

## Componentes

- `src/rag_fds/generation.py`
- `src/rag_fds/fact_extraction.py`
- `scripts/ask.py`

## Reglas de generacion aplicadas

- Runtime principal: Ollama local en `http://127.0.0.1:11434`.
- Modelo final validado: `qwen2.5:3b`.
- Para datos criticos (telefonos, CAS, ONU, EPP, imagenes/OCR), el sistema usa extraccion literal sobre los chunks recuperados antes de redactar con LLM. Esto evita cambiar puntos, comas, unidades, porcentajes, telefonos o codigos.
- El LLM recibe exclusivamente el contexto de los `top-k` chunks recuperados.
- Si no hay evidencia suficiente, debe responder:
  `No hay informacion suficiente en los fragmentos recuperados.`
- Debe incluir una seccion `Fuentes` al final.
- Cada fuente referencia: documento, seccion, paginas y `chunk_id`.

## Configuracion de entorno

```bash
brew services start ollama
ollama pull qwen2.5:3b
source scripts/env_local.sh
```

AWS/ngrok queda documentado como alternativa de despliegue, no como dependencia principal de la version final.

## Comandos

Prueba de prompt sin llamar a Ollama:

```bash
python scripts/ask.py --manufacturer SIKA --question "Numero ONU y clase de transporte" --dry-run
```

Ejecucion completa RAG + Ollama:

```bash
.venv/bin/python scripts/ask.py --manufacturer SIKA --question "Numero ONU y clase de transporte" --top-k 3
```

Salida JSON:

```bash
python scripts/ask.py --manufacturer SIKA --question "Numero ONU y clase de transporte" --json
```
