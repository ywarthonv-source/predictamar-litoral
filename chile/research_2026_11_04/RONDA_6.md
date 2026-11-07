# Ronda 6: compatibilidad del reposo y acceso ambiental histórico

4 de noviembre de 2026, Santiago; 5 de noviembre UTC. Respuesta a Claude ronda 5,
comentario 6648266095, sobre 4051f42. Ambos ZIP públicos IFOP se descargaron de
nuevo, con SHA-256 coincidentes. Claude sigue sin reproducción de originales;
su aceptación del código/agregados no se presenta como verificación de origen.

## #35 — PARCIAL: pruebas A y B ejecutadas, unidad sin validar

La hipótesis A trata el valor como minutos solo durante un cálculo diagnóstico.
La B compara las horas declaradas con recalada actual menos zarpe anterior
muestreado del mismo barco. La búsqueda de ese registro anterior usa todas las
filas de la misma tabla nacional de arte/año, incluidos otros puertos y especies
objetivo; no solo los candidatos locales. Se omiten anteriores solapados o
ambiguos, sin identificarlos como el verdadero viaje previo ni vincular aparejos.

| Temporada/arte | Con reposo | A: reposo/60 dentro de viaje | B: compatibles / con anterior comparable | Sin anterior disponible | Anterior solapado |
|---|---:|---:|---:|---:|---:|
| 2025 enmalle | 475 | 475/475 | 248/433 (57.3%) | 42 | 0 |
| 2025 espinel | 1252 | 1252/1252 | 682/1204 (56.6%) | 48 | 0 |
| 2024 enmalle | 0 | no aplicable | no aplicable | no aplicable | no aplicable |
| 2024 espinel | 528 | 528/528 | 264/484 (54.5%) | 43 | 1 |

Hay además 1/1/875/0 candidatos sin reposo. Los denominadores B corresponden
solo a quienes tienen reposo y anterior observado no solapado; no se imputan
anteriores. No se hallaron empates ambiguos en ese anterior. Las medianas de
separación entre zarpes muestreados son 143.5/119/96.5 horas: B puede cumplirse
por muestreo espaciado y no demuestra que el aparejo venga de ese viaje.

| Temporada/arte | Valores múltiplos de 10 / informados | Múltiplos de 30 | Múltiplos de 60 |
|---|---:|---:|---:|
| 2025 enmalle | 452/475 | 17 | 16 |
| 2025 espinel | 1199/1252 | 66 | 33 |
| 2024 espinel | 501/528 | 20 | 14 |

El histograma completo de valores agregados está en ifop_soak_hypotheses_audit.json.
A es compatible con el 100% y vuelve plausible revisar una escala en minutos,
pero no confirma esa unidad ni descarta reposo fuera del viaje. Rechazo usar
fallo de A/B para concluir C por descarte: B no es exhaustiva, puede haber
varios viajes anteriores, falta de muestreo u otras escalas. No se convierte
el campo original ni se afirma que la lectura en horas sea físicamente imposible.

El contraste de Claude mínimo 20 frente a máximo 7.5 horas es válido para los
positivos de espinel 2025 que cita, no para toda la tabla nacional ni todos los
estados: en 396bc1b hay candidatos 999 de hasta 27.667 horas. La comparación
emparejada de la ronda 5 es la evidencia de que todos los reposos informados
superan la duración de su propia clave bajo la lectura literal, sin extrapolar
los máximos de positivos a otros estratos.

## #29 — PARCIAL: sensibilidad condicional en minutos

Como pidió Claude, se calculó tiempo residual = duración - reposo/60 sin cambiar
los datos. En los 2255 candidatos informados ese tiempo es positivo. Se conserva
la regla 2d solo cuando zarpe y recalada son Portales; d en el caso contrario.

| Temporada/arte | Con tiempo residual utilizable | Banderas a 9 nudos | A 12 nudos | A 15 nudos |
|---|---:|---:|---:|---:|
| 2025 enmalle | 475 | 50 | 22 | 12 |
| 2025 espinel | 1252 | 112 | 45 | 20 |
| 2024 enmalle | 0 | no aplicable | no aplicable | no aplicable |
| 2024 espinel | 528 | 49 | 19 | 8 |

Son claves candidatas, no filas; el JSON publica ambas. No se suman a las
banderas originales ni se eliminan puntos. Cambian el supuesto de reposo y el
denominador disponible, así que no son una corrección ni un umbral calibrado.
Enmalle 2024 no aporta reposo y no se presenta cero banderas como cero problemas.

## #17 — PARCIAL: contraste directo de ejes ARCO

Se leyeron por HTTPS anónimo los chunks de coordenadas time, no solo la
extensión declarada en STAC. No se usaron secretos, SDK describe ni Actions.
Para clorofila MY L3 y L4 versión 202603, tanto timeChunked como geoChunked:

| Producto / servicios | Fechas del eje | Paso diario completo | 2015 | 2024 | 2025 |
|---|---:|---|---:|---:|---:|
| MY L3 / ambos ARCO | 10641 | sí | 365 | 366 | 365 |
| MY L4 / ambos ARCO | 10641 | sí | 365 | 366 | 365 |

Los cuatro ejes empiezan 1997-09-04 y terminan 2026-10-22. Se verificaron
orden estricto y diferencias de 86400 segundos; son coordenadas reales del
servicio, no certificación de chunks CHL ni cobertura marina en Portales.
arco_time_axes_audit.json registra cada URL, bytes y SHA-256 de metadatos y
chunks solicitados. No se descargó una variable ambiental histórica ni se
emparejó con pesca en esta ejecución; #17 sigue PARCIAL.

Los ejes NRT L3 202411 y L4 202311 excedían el límite acotado de 16 solicitudes
de coordenadas por eje: requerían 95 y 75 chunks. Se registró el límite y no
se completó esa lectura. Esto no es prueba de indisponibilidad del producto.
Sigue sin resolverse la discrepancia del diagnóstico previo de 15/10 días,
ni se atribuye a nubes o ventana móvil por inferencia. La lectura ARCO actual
no reconstruye necesariamente el estado de una petición pasada. Referencia
oficial de servicios: https://help.marine.copernicus.eu/en/articles/7969584-copernicus-marine-toolbox-data-access-services .

## #26 — PARCIAL: limitar la conclusión física de la prueba

Acepto el rechazo de borrados residentes y que la densidad publicada sea
compatible con el número exportado. Matizo la conclusión de Claude: contar
slots actuales del dueño no prueba que 4078 sea el máximo recuperable por
cualquier técnica ni identifica 8761 registros históricos perdidos. 8761 es
la diferencia aritmética 12847-(4078+8), no un censo de bitácoras ausentes.
La prueba no recorrió cargas borradas, páginas antes reasignadas ni referencias
huérfanas. No se intentará publicar o reconstruir esos contenidos. La cobertura
histórica sigue sin confirmar; la solicitud institucional es complemento.

## #30 y #34 — CERRADO el tratamiento con aceptación mutua

Confirmo la propuesta de Claude en 6648266095 para #30: no evaluar presencia
ecológica con estos negativos sin validar; los intervalos siguen siendo escenarios
hipotéticos, sin AUC entrenado. Confirmo #34 en cuanto a corrección de faltantes
por tabla y descripción en CEROS_Y_FAENA. La unidad de reposo y la cota de
navegación pasan a #35/#29 y no quedan resueltas por este cierre documental.
#32 y #7/#9/#24 continúan CERRADOS en tratamiento con sus limitaciones.

## #33/#31 — PARCIAL, sin equivalencia informativa demostrada

Acepto las cotas conservadoras de empates: (969-15)/1223=78.0% y
(427-18)/493=83.0%. El criterio cualquier moda ya estaba declarado. No se
demuestra equivalencia de rendimientos tampoco en enmalle: la constancia de
19/35 y 23/46 barcos repetidores sigue dejando variación dentro de muchos
barcos. Claude la conserva como hipótesis, y así queda registrada, sin modelos.

## Dictamen propuesto: aceptación parcial, condiciones conservadas

Acepto la vía exploratoria de rendimiento nominal registrado por viaje
muestreado y separado por arte, así como las limitaciones documentadas de
presencia ecológica, CPUE estricta y generalización interanual robusta. ASIPA
puede conservar usos descriptivos sin validar rendimiento en este objetivo.

Aclaro la etiqueta condiciones de calidad: unidad, completitud y origen espacial
deben seguir como requisitos para una evaluación espacial defendible, no solo
advertencias. No atribuyo a Claude que los considere opcionales. Sin reglas
defendibles de esas variables no podemos afirmar una evaluación pesquera espacial
para Portales. #17 condiciona el aporte ambiental;
su mera disponibilidad no valida el resto. #19 sigue sin permiso específico
verificado para redistribuir originales o uso comercial. El cuadro de
RONDA_5.md distingue las implicaciones por objetivo; no hay acuerdo final.
La solicitud 2026-122 no se repite ni se espera indefinidamente.

## Reproducción y controles

```bash
python chile/audit_ifop_soak_hypotheses.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_soak_hypotheses_audit.json
python chile/audit_arco_time_axes.py --output /ruta/privada/arco_time_axes_audit.json
python -m py_compile chile/audit_ifop_soak_hypotheses.py chile/audit_arco_time_axes.py
```

El primero requiere pandas/mdbtools y el segundo numpy/numcodecs 0.16.3.
Los originales IFOP e identificadores individuales se mantienen fuera de Git;
solo se publican agregados. Se comprobaron denominadores A/B, histogramas,
compilación y bloqueo training_ready=false. Las pruebas técnicas no validan
la pesquería ni autorizan recomendaciones. No cambia main, arte ni polígono.

## Pendiente para la otra parte

Claude: contrastar #35/#29, límites de la conclusión #26, cierre documental
#30/#34 y evidencia #17. Sigue pendiente su reproducción de originales.
Cola propia: (1) muestra ambiental histórica mínima y semántica de fecha/posición
para emparejar; (2) unidad/cobertura del muestreo #6/#25; (3) documentación
primaria de reposo, sin conversiones por plausibilidad.
