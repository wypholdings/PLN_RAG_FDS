# Fase 2 - Conversion PDF a Markdown

## Objetivo

Implementar un pipeline inicial para convertir FDS en PDF a Markdown estructurado, con metadatos, deteccion de secciones normativas y trazabilidad por paginas.

## Implementacion actual

Archivos principales:

- `src/rag_fds/markdown_converter.py`
- `scripts/convert_pdfs.py`
- `src/rag_fds/sections.py`
- `src/rag_fds/pdf_utils.py`

El conversor genera:

- Markdown en `data/processed/markdown/<fabricante>/`.
- Metadata JSON en `data/processed/metadata/<fabricante>/`.
- Assets visuales en `data/processed/assets/<fabricante>/<documento>/images/`.
- Reporte CSV en `data/reports/conversion_report_<fabricante>.csv`.

## Documentos convertidos

### SIKA completo

| Resultado | Cantidad |
|---|---:|
| PDFs fuente SIKA | 15 |
| Documentos Markdown canonicos | 14 |
| Duplicados registrados como alias | 1 |
| Documentos canonicos con 16/16 secciones | 14 |
| Documentos canonicos con errores de extraccion | 0 |
| Tablas extraidas como Markdown | 39 |
| Imagenes extraidas con OCR y trazabilidad | 174 |

Duplicado registrado:

- Alias: `Esmalte Uretano AR Comp. B.pdf`
- Canonico: `FDS 22 - Esmalte Uretano AR Comp. B.pdf`

Los alias quedaron registrados en `data/processed/metadata/SIKA/duplicate_aliases.json`.

Pilotos revisados inicialmente:

| Documento | Secciones | Alertas |
|---|---:|---|
| `FDS 27 - Epoxi_100HS_S300_CA.pdf` | 16/16 | Ninguna |
| `FDS 20 - Esmalte Alquidico Serie 31.pdf` | 16/16 | Ninguna |
| `FDS 69 - Esmalte Uretano Part A - SIKA.pdf` | 16/16 | Ninguna |

### Pintuco piloto

| Documento | Secciones | Alertas |
|---|---:|---|
| `FDS 41 - PINTURA ACRILICA CONSTRUCCION ALTA ASEPSIA BLANCO 27580 - PINTUCO .pdf` | 16/16 | Orden de extraccion no ascendente |

La alerta de Pintuco fue generada antes de extender el pipeline visual. La conversion formal usa PyMuPDF, Tesseract y metadatos estructurales para preservar tablas, imagenes y trazabilidad.

## Calidad alcanzada

- SIKA completo cumple el criterio obligatorio de 16 secciones en todos los documentos canonicos.
- Cada Markdown incluye front matter con metadatos.
- Cada seccion incluye nota de trazabilidad con pagina o rango de paginas.
- Cada tabla extraida se agrega como tabla Markdown dentro de la seccion asociada.
- Cada imagen extraida se guarda como asset, se referencia desde Markdown y tiene una nota de trazabilidad debajo.
- Cada imagen tiene OCR local con Tesseract (`spa+eng`) o registro explicito de ausencia de texto legible.
- Se filtran encabezados repetidos de pagina para evitar contaminar chunks futuros.
- El detector evita falsos positivos de referencias internas como "seccion 13)".
- La conversion SIKA fue validada con `scripts/validate_conversion.py` y obtuvo 14/14 documentos aprobados.

Reporte de calidad:

- `data/reports/quality_report_sika.csv`
- `data/reports/quality_summary_sika.json`

## Controles aplicados

- La deduplicacion se aplica en conversion masiva por hash de texto.
- Las tablas se extraen con PyMuPDF `find_tables()` y se serializan en Markdown.
- Las imagenes, logos, pictogramas e iconos embebidos se extraen con PyMuPDF, se guardan como archivos y se registran en metadata.
- El OCR se ejecuta localmente con Tesseract y paquetes de idioma `spa+eng`.
- La asociacion de tablas e imagenes a secciones se hace por proximidad espacial y metadatos de pagina.

## Siguiente etapa

El siguiente paso es construir chunks para RAG:

- dividir por seccion y subchunk cuando una seccion sea larga,
- conservar metadatos de documento, fabricante, producto, seccion y paginas,
- generar un archivo JSONL de chunks,
- preparar el indice vectorial local.

Pintuco debe mantenerse como extension y procesarse con el mismo pipeline extendido usado para SIKA.
