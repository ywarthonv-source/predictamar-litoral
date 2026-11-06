# Cruce descriptivo por recalada, merluza de Portales 2026

6 de noviembre de 2026. Se ejecutó sobre el ZIP privado y el JSON de clorofila [fijado en la ronda 46](https://github.com/ywarthonv-source/predictamar-litoral/blob/d3b5da48fa7e3537c282e0574f1a07cbac396f51/chile/research_2026_11_04/saip_chl_arco_2026.json).

`python chile/audit_saip_daily_landings.py /ruta/privada/Informacion_SAIP.zip chile/research_2026_11_04/saip_chl_arco_2026.json`

## #68 · PARCIAL

La única fila de noviembre cae en el tramo 1–3, sin publicar el día exacto. NRT aporta un valor para 1 de las 19 filas posteriores al eje MY. El eje válido NRT termina el 5 de noviembre y la extracción se detuvo el 3. El código verifica que todas las recaladas están dentro de la ventana solicitada, por lo que los 163 días de recalada clasificados fuera de eje NRT están antes de su inicio válido, no después de la ventana solicitada. La clasificación publicada es válida para estas recaladas. No se usa NRT para rellenar MY en el análisis principal.

## #69 · PARCIAL

Enero–abril aporta 1.290/2.261 filas (57,1 %) y 1.171/1.751 emparejadas (66,9 %). La proporción cambia en 9,8 puntos porcentuales. Por ello, la unidad descriptiva es el día de recalada dentro de mes y arte. Antes de calcular las asociaciones se fijó un mínimo descriptivo de ocho días emparejados por estrato, sin interpretarlo como umbral de potencia. No se completaron días sin filas o sin clorofila.

Con ese criterio, 15 de 19 estratos observados permiten un resumen. Junio queda debajo para ambos artes (4 y 6 días), julio para espinel (7) y noviembre para enmalle (0). Mayo en espinel cumple exactamente con ocho. Septiembre se mantiene separado por veda y sin imputación de cero.

La correlación descriptiva de Spearman entre clorofila y kilos diarios varió de −0,381 a 0,406. También se calculó para kilos medios por fila y número diario de filas. En agosto, enmalle, las tres correlaciones fueron 0,406, 0,152 y 0,487 en diez días. En octubre, enmalle, fueron 0,322, 0,063 y 0,156 en doce días. Esto no establece una asociación consistente entre estratos. El número de filas y los kilos medios por fila no miden esfuerzo ni CPUE. La anomalía #61 no entra en la muestra emparejada. [Agregados reproducibles](saip_daily_landings_2026.json).

El dictamen por faena sigue condicionado a registros que vinculen fecha, posición y captura de la misma operación, con esfuerzo y ceros verificables para evaluaciones que los requieran. Este ejercicio no entrena un modelo.
