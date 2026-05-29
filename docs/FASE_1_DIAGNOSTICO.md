# Fase 1 - Diagnostico del corpus

## Objetivo

Inventariar el corpus obligatorio SIKA y el corpus adicional Pintuco para medir calidad de extraccion, presencia de duplicados, deteccion de secciones normativas y seleccion de documentos piloto.

## Resultados

| Fabricante | PDFs | Paginas | PDFs con 16 secciones | Errores de extraccion | Grupos duplicados |
|---|---:|---:|---:|---:|---:|
| SIKA | 15 | 159 | 15 | 0 | 1 |
| Pintuco | 21 | 241 | 20 | 0 | 2 |

Reportes generados:

- `data/reports/inventory.csv`
- `data/reports/inventory.json`
- `data/reports/inventory_summary.json`

## Duplicados detectados

### SIKA

- `Esmalte Uretano AR Comp. B.pdf`
- `FDS 22 - Esmalte Uretano AR Comp. B.pdf`

Estos archivos tienen el mismo hash de archivo y el mismo hash de texto. Para el indice final se debe conservar uno como documento canonico y registrar el otro como duplicado.

### Pintuco

- `FDS 12 - PINTURA ANTICORROSIVA GRIS 507 _ 10014333-10012454-10171712 _COL (Version 3) (1).pdf`
- `FDS 6 - PINTURA ANTICORROSIVA GRIS 507 _ 10014333-10012454-10171712 _COL (Version 3).pdf`

Segundo grupo:

- `FDS 21 - Pintura-para-trafico-acrilico-base-solvente-13722-10017277-10015687.pdf`
- `FDS 21 -pintura-para-trafico-acrilico-base-solvente-13722-10017277-10015687.pdf`

## Documento Pintuco con alerta

`FDS 79 - PQ CORROTEC PREMIUM 507 GRIS - PINTUCO - AKSONOBEL.pdf`

- Secciones detectadas: 10 de 16.
- Secciones faltantes segun detector: 1, 2, 3, 5, 14, 16.
- Decision: revisarlo con el pipeline extendido de tablas, imagenes y OCR cuando se procese Pintuco como extension.

## Documentos piloto recomendados

### SIKA obligatorio

1. `FDS 27 - Epoxi_100HS_S300_CA.pdf`
   - 8 paginas.
   - 16 secciones detectadas.
   - Buen candidato para primera conversion por ser corto.

2. `FDS 20 - Esmalte Alquidico Serie 31.pdf`
   - 10 paginas.
   - 16 secciones detectadas.
   - Producto distinto para validar generalizacion dentro de SIKA.

3. `FDS 69 - Esmalte Uretano Part A - SIKA.pdf`
   - 13 paginas.
   - 16 secciones detectadas.
   - Buen candidato para probar documentos mas largos.

### Pintuco adicional

1. `FDS 41 - PINTURA ACRILICA CONSTRUCCION ALTA ASEPSIA BLANCO 27580 - PINTUCO .pdf`
   - 8 paginas.
   - 16 secciones detectadas.
   - Buen primer documento para validar que el pipeline funciona fuera de SIKA.

2. `FDS 79 - PQ CORROTEC PREMIUM 507 GRIS - PINTUCO - AKSONOBEL.pdf`
   - Documento con alerta.
   - Util para probar manejo de documentos dificiles, pero no debe bloquear el cumplimiento principal.

## Decisiones para maxima nota

- SIKA se procesa completo y se evalua como entrega obligatoria.
- Pintuco se presenta como extension de escalabilidad, no como reemplazo de SIKA.
- Los duplicados no se deben indexar dos veces; se registran como alias del documento canonico.
- La app de demo debe poder consultar corpus preprocesado y tambien aceptar PDFs cargados manualmente.
- El sistema debe responder "no encontrado en las fuentes recuperadas" cuando no haya evidencia suficiente.

## Necesidades para Ollama

Para la version final se usa Ollama local como runtime principal:

- Ollama instalado.
- Servicio local activo en `http://127.0.0.1:11434`.
- Modelo `qwen2.5:3b` descargado.
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`.

AWS/ngrok queda como alternativa documentada, no como dependencia principal.
