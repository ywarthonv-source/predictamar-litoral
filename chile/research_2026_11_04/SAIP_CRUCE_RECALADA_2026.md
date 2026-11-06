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

## #70 · Sensibilidad e interpretación

Se reprodujo el diagnóstico de permutación sobre vectores privados con empates reales mediante `python chile/audit_saip_daily_landings.py /ruta/privada/Informacion_SAIP.zip chile/research_2026_11_04/saip_chl_arco_2026.json --iid-diagnostic`. Usa 40.000 permutaciones por estrato, rangos medios y semilla 70. El [derivado](saip_daily_iid_diagnostic_2026.json) guarda las colas bilaterales en el orden kilos diarios, kilos medios por fila y número diario de filas. El mínimo fue 0,05967 (febrero, enmalle, número diario de filas). Ninguna de las 45 colas diagnósticas quedó bajo 0,05.

El barajado libre supone intercambiabilidad. En la serie ambiental, los 150 pares de días calendarios consecutivos con datos positivos tienen correlación 0,4127 de Pearson en log10 y 0,4650 de Spearman. Se reproduce tomando pares de fechas a un día exacto del JSON ambiental y aplicando `np.corrcoef(a,b)[0,1]` y `scipy.stats.spearmanr(a,b).statistic` a los logaritmos. Esa dependencia es una razón para no usar el diagnóstico como prueba formal. Tampoco se calculó potencia ni se pueden excluir magnitudes de efecto a partir de un umbral de significación. Los dos artes comparten la serie ambiental y el signo de los estratos no es evidencia independiente.

| Mínimo de días | Estratos | Rango de rho para kilos diarios | Mediana |
|---|---:|---:|---:|
| 8 | 15 | −0,3810 a 0,4061 | 0,0860 |
| 10 | 12 | −0,1121 a 0,4061 | 0,1185 |
| 12 | 9 | −0,1121 a 0,3217 | 0,0860 |
| 15 | 7 | −0,0158 a 0,2659 | 0,0860 |

La tabla se reproduce filtrando `strata` por `days >= mínimo` y resumiendo `rho_daily_kg`. El mínimo de ocho días se mantiene como regla descriptiva. Los filtros más estrictos son sensibilidad posterior y cambian qué estratos entran. No apareció un patrón estable de asociación en 2026. Esto no identifica un efecto nulo. La exploración por recalada es viable con los límites descritos, en bloques IFOP y SAIP separados. La evaluación por faena, presencia/ausencia o CPUE estricta sigue sin un conjunto admisible.
