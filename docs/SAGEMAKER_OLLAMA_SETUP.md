# SageMaker + Ollama para este proyecto

Este documento queda como anexo historico/alternativo. La version final validada usa Ollama local en `http://127.0.0.1:11434`.

## Estado del notebook legado

Archivo auditado: `/Users/danielwilches/Downloads/Dino_Description.ipynb`

Partes reutilizables:

- Verificacion de contenedor `ollama` en Docker.
- Descarga del modelo (`ollama pull ...`).
- Llamadas HTTP a `http://localhost:11434/api/generate`.

Partes que no debemos reutilizar tal cual:

- Celda con `pyngrok` y token embebido.
- Escritura de endpoint basada en URL publica de ngrok.

## Riesgo inmediato

El notebook tiene un `ngrok auth token` en texto plano.

Accion obligatoria:

1. Revocar ese token en el panel de ngrok.
2. No volver a guardar tokens en notebooks ni en el repo.

## Recomendacion para este proyecto

Usar **port-forward local** en vez de endpoint publico.

Ventajas:

- No expones Ollama a internet.
- Menor dependencia de terceros.
- Flujo estable para demo y desarrollo.

## Opcion A (recomendada): AWS SSM Port Forwarding

Requisitos:

- Instancia con rol/permisos SSM.
- Agente SSM activo.

Comando desde tu maquina:

```bash
aws ssm start-session \
  --target <INSTANCE_ID> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["127.0.0.1"],"portNumber":["11434"],"localPortNumber":["11434"]}'
```

Con eso, en este repo:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
```

## Opcion B: SSH tunnel

```bash
ssh -N -L 11434:127.0.0.1:11434 ec2-user@<PUBLIC_IP_OR_DNS>
```

Y en el repo:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
```

## Verificacion minima

Desde tu maquina local (con el tunnel arriba):

```bash
curl -s http://127.0.0.1:11434/api/tags
```

Debe responder JSON con la lista de modelos.

## Modelo recomendado para Fase 5

- Base: `qwen2.5:7b-instruct` (mejor calidad para QA tecnico).
- Alternativa ligera: `qwen2.5:3b-instruct`.

Descarga en SageMaker:

```bash
docker exec ollama ollama pull qwen2.5:7b-instruct
docker exec ollama ollama list
```

## Integracion con el repo actual

Para pasar a Fase 5 yo necesito solo:

1. `OLLAMA_BASE_URL` funcional.
2. Nombre exacto del modelo en `ollama list`.

Con eso implemento la capa de generacion con citas obligatorias sobre el retriever ya validado.
