# Informe Final - RAG_FDS Grupo I (SIKA)

## 1. Objetivo y alcance

Se implemento un sistema RAG para Fichas de Datos de Seguridad (FDS) del fabricante asignado al Grupo I: **SIKA**.  
El sistema cubre extraccion documental, conversion a Markdown, validacion estructural, chunking, indexacion, recuperacion y generacion con trazabilidad.  
Se incluyo soporte de fabricante adicional y carga manual de PDFs en la demo para mostrar generalizacion.

## 2. Arquitectura final implementada

1. Extraccion PDF local con PyMuPDF + pypdf.
2. Deteccion y validacion de las 16 secciones normativas.
3. Extraccion de tablas y conversion a Markdown.
4. Extraccion de imagenes/pictogramas/logos + OCR local (`spa+eng`).
5. Asociacion estructurada de tablas/imagenes a secciones por pagina/proximidad.
6. Chunking por seccion con metadatos y trazabilidad.
7. Indice hibrido local (embeddings + TF-IDF + cobertura de terminos + boost por seccion).
8. Generacion con Ollama local (`qwen2.5:3b`) sobre contexto recuperado.
9. Demo Streamlit con corpus preprocesado y carga manual de PDFs.

Runtime final:

- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=qwen2.5:3b`
- `source scripts/env_local.sh` para fijar variables locales del runtime.
- Servicio local validado con `brew services start ollama`.

## 3. Cumplimiento de requerimientos de la guia

- Pipeline PDF -> Markdown: **cumplido**.
- Preservacion estructural (titulos, tablas, listas, notas): **cumplido**.
- Identificacion de 16 secciones: **cumplido para corpus canonico SIKA**.
- Tratamiento de imagenes y OCR local: **cumplido**.
- Asociacion imagen-seccion-tabla y nota de trazabilidad: **cumplido**.
- Sistema RAG funcional con modelos/infraestructura propia: **cumplido**.
- Estrategia de chunking documentada: **cumplido**.
- Consultas con trazabilidad a fuente: **cumplido**.
- Ground truth y evaluacion comparativa: **cumplido con dataset y script de evaluacion**.

## 4. Resultados de procesamiento y calidad

Resumen principal del corpus SIKA (ver reportes en `data/reports`):

- 14 documentos canonicos procesados.
- 224 secciones normativas validadas.
- 39 tablas extraidas.
- 174 imagenes extraidas con OCR local.
- 224 chunks RAG validados.

Pruebas de retrieval previas:

- 5/5 consultas de control con seccion correcta en top-1.

Validacion automatica final:

- Conversion SIKA: 14/14 documentos pasan, calidad promedio 100.0.
- Chunking: 224/224 secciones cubiertas, 39/39 tablas cubiertas, 174/174 imagenes cubiertas.
- Retrieval smoke test: 5/5 top-1 correcto.

## 5. Ground truth y evaluacion RAG

Se construyo un set de 25 pares pregunta-respuesta:

- Archivo: `data/ground_truth/sika_ground_truth_25.json`.
- Cubre preguntas factuales, tecnicas y de trazabilidad.
- Incluye seccion esperada y terminos esperados por pregunta.

Script de evaluacion:

- `scripts/evaluate_ground_truth.py`
- Modo `retrieval_only` (estable, sin dependencia de red/LLM).
- Modo `with_llm` (evalua tambien respuesta generada).

Salidas:

- `data/reports/ground_truth_eval_sika_retrieval_only.csv|json`
- `data/reports/ground_truth_eval_sika_with_llm.csv|json`

Resultados finales:

```json
{
  "retrieval_only": {
    "ground_truth_items": 25,
    "top1_section_accuracy": 1.0,
    "topk_section_recall": 1.0,
    "context_term_coverage_pass_rate": 1.0
  },
  "with_ollama": {
    "ground_truth_items": 25,
    "llm_answers_evaluated": 25,
    "top1_section_accuracy": 1.0,
    "topk_section_recall": 1.0,
    "context_term_coverage_pass_rate": 1.0,
    "answer_term_pass_rate": 1.0
  }
}
```

## 6. Limitaciones observadas

1. Las preguntas abiertas que requieren criterio no definido por la FDS (por ejemplo, "el quimico mas peligroso") no deben responderse como hecho documental.
2. La extraccion OCR puede registrar "OCR sin texto legible" cuando una imagen no contiene texto interpretable.
3. Las consultas comparativas amplias pueden requerir dividir la pregunta por seccion para mantener trazabilidad estricta.

## 7. Mitigaciones implementadas

1. Ollama local como runtime principal para eliminar dependencia de ngrok en la entrega.
2. Streaming de respuesta con `/api/generate`.
3. Reintentos automáticos y degradacion controlada de contexto.
4. Extraccion literal para telefonos, CAS, ONU, EPP, imagenes/OCR y trazabilidad de seccion.
5. Regla de no alucinacion: sin evidencia suficiente, respuesta explicita de insuficiencia.

## 8. Demostracion funcional

App Streamlit:

- Archivo: `streamlit_app.py`
- Funciones:
  - consulta sobre corpus preprocesado,
  - carga manual de PDFs y reprocesamiento en vivo,
  - respuesta con fuentes y trazabilidad detallada.

## 9. Conclusiones

El proyecto implementa una arquitectura RAG reproducible y portable alineada con la guia RAG_FDS.  
Se priorizo fidelidad documental y trazabilidad sobre respuestas especulativas.  
La version final usa Ollama local como runtime principal y valida el sistema contra 25 preguntas ground truth con resultados completos.
