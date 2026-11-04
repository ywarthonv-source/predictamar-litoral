# PredictaMAR Chile — Caleta Portales
Actualización: 4 de noviembre de 2026. Estado: investigación y auditoría de datos; sin recomendaciones operativas chilenas.

Randy confirmó como objetivos **reineta (Brama australis)** y **merluza común (Merluccius gayi gayi)**. Se verificó el punto oficial de Portales (Subpesca, código 214). El área de pesca, arte actual de cada grupo y embarcaciones del piloto aún no están fijados.

## Resultado disponible
Leer primero [la respuesta a la revisión independiente](research_2026_11_04/RESPUESTA_AUDITORIA.md) y después [el informe de hallazgos actualizado](research_2026_11_04/RESULTADOS.md). La entrega contiene:
- Recorrido de las tres tablas ASIPA demersales 1.5 e interpretación biológica todavía parcial, con filtros de ambas especies y Portales.
- CSV histórico de Sernapesca examinado: la etiqueta Valparaíso no separa Caleta Portales.
- Dos bases Access de IFOP (cruceros 2024 y 2025) descargadas, exportadas y auditadas.
- Descargas reales de siete productos Copernicus para un recuadro técnico de Valparaíso en octubre de 2026. Cinco cubren 30/30 fechas; clorofila L3 y L4 tienen cobertura temporal parcial.
- Scripts reproducibles, doce comprobaciones científicas, incluidas tres sobre archivos reales y manifiesto de fuentes/checksums.

Los datos crudos y las filas detalladas se conservan fuera del repositorio público. Las licencias y condiciones de cada fuente deben resolverse antes de su uso comercial. Las cantidades de registros no equivalen a viajes independientes ni a eficacia predictiva.

## Reproducir
Instalar `python -m pip install -r chile/requirements-research.txt`. La lectura de Access requiere `mdbtools` (probado con 1.0.0).

```bash
python chile/download_public_sources.py --destination /ruta/fuera/del/repositorio
python chile/audit_public_data.py --raw-dir /ruta/fuera/del/repositorio --output-dir /ruta/auditoria
```
Para los cruceros, descomprimir cada anexo en su propia carpeta bajo el directorio de datos, sin extraer entradas `__MACOSX`; después:

```bash
python chile/audit_cruise_databases.py --raw-dir /ruta/fuera/del/repositorio --output /ruta/auditoria/cruise_audit.json
python -m unittest discover -s chile -p 'test_research_audit.py' -v
```
`diagnose_copernicus.py` usa las credenciales normales de Copernicus desde el entorno y no solicita ni publica contraseñas. El workflow de investigación usa los secrets ya existentes del repositorio; no modifica la publicación peruana ni programa corridas periódicas.

## Siguiente decisión técnica
Priorizar merluza común para depurar el primer conjunto evaluable, manteniendo reineta como segunda línea. Separar las encuestas artesanales de los cruceros de arrastre. Excluir conflictos y fechas inválidas, verificar unidades/esfuerzo y documentar cualquier corrección antes de emparejar ambiente y pesca.

Los pesos, curvas, horarios y precisión de Pucusana no se trasladan a Chile. El contrato `pilot_contract.json` sigue siendo declarativo: ninguna ruta operativa carga ese archivo. La revisión independiente de Claude fue recibida de Randy. Sus hallazgos críticos se contrastaron con los originales; quedan pendientes semántica de fuente, diferencias metodológicas y aprobación posterior de las correcciones.

## Conciliación tras la auditoría de Claude
`reconcile_review.py` compara los bloques 14-01 y 15-01, conserva las dos fechas y crea un registro privado de enlaces candidatos sin colapsar operaciones ambiguas. No utiliza *absent* del bloque biológico como captura cero. La igualdad de fecha-hora-posicion no sustituye un identificador de viaje/embarcación.

```bash
python chile/reconcile_review.py --raw-dir /ruta/fuera/del/repositorio --output-dir chile/research_2026_11_04
CHILE_RAW_DIR=/ruta/fuera/del/repositorio python -m unittest discover -s chile -p 'test*.py' -v
```

El nuevo proxy L3/L4 describe disponibilidad: no certifica una máscara física de mar, nubes ni la procedencia individual de cada píxel. Los originales permanecen sin cambios.
