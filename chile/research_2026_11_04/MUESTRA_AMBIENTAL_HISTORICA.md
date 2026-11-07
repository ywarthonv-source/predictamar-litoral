# Muestra mínima de clorofila histórica

5 de noviembre de 2026, Santiago. Avance independiente de la ronda 6; no es
una nueva ronda de auditoría ni añade desacuerdos. #17 permanece PARCIAL.

## Qué se investigó

Se comprobó acceso real a valores CHL de los productos MY L3 y L4 versión
202603, servicio timeChunked. Las fechas se fijaron antes de leer los valores:
2015-01-15, 2024-01-15 y 2025-01-15. La primera responde a la comprobación
histórica propuesta por Claude; las otras prueban un día de cada temporada
IFOP disponible. No se eligieron por éxito de cobertura.

Se conserva el recuadro técnico ya usado (-33.3 a -32.8 de latitud y -72.1 a
-71.6 de longitud), no un polígono de faena aprobado. La grilla nativa aporta
12 por 12 celdas. Ambas series comparten coordenadas y unidades, comprobadas
por huellas de los vectores seleccionados. Límites de centros realmente
seleccionados: latitud -33.2708358765 a -32.8125038147; longitud -72.0625 a
-71.6041641235. No se redondearon coordenadas para vincularlas a pesca.

## Valores descargados y tratamiento

| Fecha | Celdas L3 finitas dentro de límites del proveedor / 144 | L4 / 144 | L4 finitas sin L3 | Máxima diferencia absoluta en celdas comunes |
|---|---:|---:|---:|---:|
| 2015-01-15 | 2 | 128 | 126 | 0 |
| 2024-01-15 | 36 | 128 | 92 | 0 |
| 2025-01-15 | 70 | 128 | 58 | 0 |

Unidad publicada: milligram m-3. Los metadatos de ambos CHL declaran
coverage_content_type=modelResult; no se convierte esa etiqueta en evidencia
de observación independiente. Las medianas L3/L4 son, respectivamente,
0.627860/0.596818, 0.867016/0.889754 y 0.967713/0.921841 en esas fechas.
Rangos y metadatos están en arco_historical_chl_probe.json.

Se descargaron seis objetos CHL, tres por producto: 5.920.243 bytes totales
incluyendo los metadatos y coordenadas usados en ambos productos. No hubo
HTTP 404 en esos objetos. El manifiesto registra URL, tamaño y SHA-256 de cada
respuesta; no se publica un archivo crudo ni una credencial.

El lector respeta dimensiones, orden, separador de chunk y codecs de Zarr v2.
Enmascara relleno -999, missing_value y valores no finitos/fuera de los límites
publicados (0 a 1000), sin sustituirlos por cero. Se conserva cero si es un valor
permitido. No se descargaron ni aplicaron flags auxiliares o incertidumbre CHL.
La proporción finita no significa que todos esos valores hayan pasado una
validación oceanográfica completa.

## Conclusión provisional y límites

Hay acceso reproducible a valores ambientales históricos de esos dos
productos en tres fechas del recuadro de diagnóstico. Esto supera la lectura
previa de ejes temporales, pero no es un censo de cobertura histórica ni una
evaluación pesquera emparejada. Solo hay un día de enero por año probado.

Los 144 denominadores incluyen posibles celdas terrestres: no son superficie
marina independiente. Las 128 celdas L4 no se usan como máscara marina.
No se atribuye la falta L3 a nubes por este ensayo. La continuidad y las celdas
adicionales L4 no son observaciones ópticas independientes; su coincidencia
con L3 donde ambos existen tampoco valida su exactitud. La clorofila superficial
no es evidencia de merluza, biomasa o cardúmenes ni valida hábitat subsuperficial.

Sigue pendiente emparejar con fechas y posiciones pesqueras de semántica
resuelta, evaluar cobertura sobre el soporte real y aplicar controles de
calidad adecuados. Tampoco se resolvió la causa del eje NRT corto del
diagnóstico inicial ni se ejecutó SDK describe o una petición autenticada.
#17 sigue PARCIAL; no se cierran otros hallazgos ni se elige arte/polígono.

## Reproducción y comprobaciones

```bash
python chile/audit_arco_historical_probe.py --output /ruta/privada/arco_historical_chl_probe.json
python -m py_compile chile/audit_arco_historical_probe.py
```

Requiere numpy/numcodecs 0.16.3 y el helper audit_arco_time_axes.py. Se ejecutó
por HTTPS anónimo, sin usar secretos GitHub ni Actions. El script limita el
recuadro, las tres fechas y hasta ocho chunks CHL por producto. Se comprobaron
los seis objetos, igualdad de coordenadas/unidades, denominadores, compilación
y un control sintético que distingue -999/NaN/fuera de límites de cero válido.
training_ready permanece false: las pruebas de lectura no validan la pesquería.

Fuente de productos y versiones: URLs STAC/ARCO en el manifiesto agregado.
Especificación primaria del formato de lectura:
https://zarr-specs.readthedocs.io/en/latest/v2/v2.0.html .

## Pendiente para la otra parte

Claude: reproducir la lectura y el enmascarado, contrastar el alcance de los
denominadores y la interpretación de L4; no cerrar #17 como evaluación ambiental.
Cola propia: (1) unidad/semántica de fecha y posición #6/#25; (2) contrato de
conjunto candidato con incertidumbres y cuarentenas explícitas; (3) emparejamiento
ambiental y calidad sobre fechas pesqueras defendibles, sin entrenar modelos.
