# Control de calidad

## Objetivo

Comprobar que el trabajo realizado no solo genera archivos, sino que cumple criterios verificables de fidelidad documental, trazabilidad y consistencia tecnica.

## Validaciones automaticas

El script principal es:

```bash
python scripts/validate_conversion.py --manufacturer SIKA
```

Genera:

- `data/reports/quality_report_sika.csv`
- `data/reports/quality_summary_sika.json`

## Criterios evaluados

Cada documento convertido se valida con estas reglas:

- Existe el Markdown esperado.
- Existe el PDF fuente.
- El hash del archivo PDF coincide con la metadata.
- El hash del texto extraido coincide con la metadata.
- El numero de paginas coincide con el PDF.
- El nombre del producto no es generico.
- El front matter incluye campos obligatorios.
- Hay exactamente 16 secciones.
- Las secciones son 1 a 16 y estan ordenadas.
- El Markdown contiene 16 encabezados de seccion.
- Cada seccion tiene nota de trazabilidad.
- Las tablas extraidas tienen representacion Markdown.
- Cada tabla tiene nota de trazabilidad.
- Cada imagen extraida existe como archivo en `data/processed/assets`.
- Cada imagen tiene metadatos estructurados: pagina, seccion asociada, tipo, hash, dimensiones y OCR.
- Cada imagen tiene nota de trazabilidad debajo de la referencia en Markdown.
- No hay secciones vacias.
- Los rangos de pagina son validos.
- No hay errores de extraccion.
- No hay alertas de conversion.

Tambien se validan los alias de duplicados:

- El documento canonico existe.
- El hash de texto del alias coincide con el canonico.
- No existen assets visuales huerfanos ni faltantes frente a la metadata.

## Resultado actual SIKA

```json
{
  "manufacturer": "SIKA",
  "documents_validated": 14,
  "documents_passed": 14,
  "documents_for_review": 0,
  "average_quality_score": 100.0,
  "duplicate_aliases": 1,
  "alias_errors": [],
  "asset_errors": []
}
```

Interpretacion:

- Los 14 documentos canonicos SIKA pasan todos los controles.
- El PDF duplicado esta registrado como alias y no se indexara dos veces.
- La conversion esta lista para alimentar el chunking del RAG.
- El corpus SIKA convertido contiene 39 tablas extraidas como Markdown.
- El corpus SIKA convertido contiene 174 imagenes extraidas, guardadas y referenciadas con OCR local y trazabilidad estructurada.

## Revision manual recomendada

La validacion automatica no reemplaza una revision humana de fidelidad visual. Para sustentar mejor la entrega, se recomienda revisar manualmente una muestra:

- 2 documentos cortos.
- 1 documento largo.
- 1 seccion con informacion tecnica densa, por ejemplo seccion 8 o 9.
- 1 seccion de transporte o regulatoria, por ejemplo seccion 14 o 15.

En esa revision se compara PDF vs Markdown y se documentan diferencias en el informe final.

## Criterio de cumplimiento

El documento guia exige preservar estructura, tablas, listas, notas y referencias cruzadas a imagenes o fuentes externas. Tambien exige asociar cada imagen a una tabla, seccion o bloque tecnico mediante proximidad espacial, referencias textuales o metadatos estructurales. La validacion automatica comprueba esos puntos para los artefactos generados de SIKA.
