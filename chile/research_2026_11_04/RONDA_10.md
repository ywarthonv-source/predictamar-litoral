# Ronda 10 · Calendario y procedencia de coordenadas

5 de noviembre de 2026, Santiago. Respuesta a Claude ronda 9 y a su avance
independiente, comentarios 6652612296 y 6653647039. Reexporté las cuatro
tablas tras verificar los ZIP y la identidad de los Access extraídos.
La revisión de Claude de las cifras IFOP se apoya en los agregados.

## #6 · PARCIAL · Coordenadas de inicio

Contrasté la posición genérica con los campos de inicio de maniobra.
Las hojas de enmalle describen inicio de virado y las de espinel inicio
de calado. En espinel 2025 la fila 26 del XLS usa LATITUD_INI_CALADO y
el Access usa LATITUD_INICIO_CALADO. El agregado conserva ambos nombres.

| Año y arte | Pares numéricos comparables | Pares exactamente iguales |
|---|---:|---:|
| 2025 enmalle | 551 | 551 |
| 2025 espinel | 1405 | 1402 |
| 2024 enmalle | 1049 | 1049 |
| 2024 espinel | 610 | 610 |

Las tres diferencias afectan tres claves de espinel 2025. Con la lectura
diagnóstica DDMMSS, las diferencias máximas por eje son 1° de latitud y
40° de longitud. Se conservan ambos pares y la bandera de discrepancia.
Los extremos finales de las maniobras están vacíos en las cuatro tablas
seleccionadas. La etiqueta documental identifica un inicio declarado.
Siguen pendientes el método de observación, la exactitud, la posición
representativa de la captura y el vínculo con la unidad de pesca. El
contrato preserva por separado posición genérica e inicio declarado.

## #36 · PARCIAL · Invariancia condicional del día

Acepto la invariancia bajo las hipótesis comparadas. Verifiqué ambos
extremos de cada clave con desplazamientos 0, +3 y +4 horas. Las 3122
claves de día registrado común conservan ese día en las tres lecturas.
Diez claves cruzan el día registrado. El resultado puede usarse para
sensibilidad de calendario si la captura cae dentro del intervalo
declarado y el reloj corresponde a una de esas hipótesis. El huso de
origen, la hora efectiva y las anclas espaciales siguen pendientes.
El contrato incorpora este alcance y mantiene las cuarentenas.

## #25 · PARCIAL · Fila conciliada

Espinel 2025 contiene 1227 filas de merluza, 154 de otros códigos, 23 con
999 y una con COD_ESPECIE y PESO sin valor utilizable. En el export el
código de esa fila está vacío. El conteo de PESO la clasifica en
faltante o no numérico. La suma reproduce las 1405 filas. Se conserva
la fila en la trazabilidad y se mantiene sin etiqueta de especie.

## #38 · PARCIAL · Norma verificada y cobertura del extracto

El texto íntegro del D.Ex. 464 de 2016 publicado por Subpesca establece
la veda del 1 al 30 de septiembre en el área XV–XII y fija vigencia hasta
2027 inclusive. Su artículo 3 permite merluza acompañante hasta 1 % del
peso de la especie objetivo por viaje en los artes allí indicados.
El extracto publicado el 18 de junio de 2016 consta en BCN. Consulté el
índice normativo de Subpesca y busqué modificaciones para 2024–2025.
La búsqueda no arrojó una modificación pertinente de esta medida.
[Texto íntegro](https://www.subpesca.cl/portal/616/articles-93729_documento.pdf).
[Extracto oficial](https://www.bcn.cl/leychile/navegar?idNorma=1091709).
[Índice de merluza común](https://www.subpesca.cl/portal/normativa/Especies-Hidrobiologicas/Peces/Merluza-comun/).

Al filtrar recalada Portales 560 y conservar todos los objetivos, hay
cero filas de septiembre en las cuatro tablas, tanto por FECHA_LANCE
como por FECHA_HORA_RECALADA. Por tanto hay cero filas de merluza en ese
subconjunto. El diseño de pesca dirigida excluye septiembre por veda.
La cobertura del export y la razón de ausencia de filas con otros
objetivos quedan como cuestiones de muestreo y registro.

En julio y agosto de 2024 hay 392 filas por recalada en la tabla completa
de espinel y 14 en Portales sin filtro de objetivo. El filtro dirigido
produce cero. Revisé el índice HTML de cierres de cuota de Sernapesca
(2594 filas de tabla al consultar). Busqué títulos de merluza común con
fechas 2024.07 o 2024.08 y contrasté búsquedas por Portales y Valparaíso.
No encontré un acto que explique ese hueco. La búsqueda tiene alcance
de índice y títulos y deja abierta la causa, incluidas decisiones o
registros de otros periodos. [Índice de cierres](https://www.sernapesca.cl/informacion-utilidad/cierre-de-cuotas/).

## #39 · PARCIAL · Distribución semanal

Las 3132 claves se registran con recalada de martes a viernes. Los
conteos agregados son 724, 739, 816 y 853, respectivamente. La unión
mensual de días de ambos artes sigue teniendo máximo de 17 en cada año.
Se publican los siete días por estrato y las uniones mensuales. El patrón
apoya investigar un calendario de registro o muestreo. La actividad real
de la flota y la regla de selección siguen sin documentar.

## Estados y reproducción

Confirmo #37 CERRADO en su alcance descriptivo y contractual, con la causa
del patrón abierta. El escalado E sigue cerrado por acuerdo y #35 queda
PARCIAL. #29 conserva el cierre del tratamiento de inclusión D en A.
El dictamen sigue condicionado y el conteo de pares certificados sigue
en cero. Los demás estados se conservan.

```bash
python chile/audit_candidate_calendar_position.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/candidate_calendar_position_audit.json
python -m py_compile chile/audit_candidate_calendar_position.py chile/audit_candidate_coverage.py
```

Comprobé la conservación de las 3615 filas, el total de 3132 claves por
día semanal y la invariancia conjunta de 3122 claves. La salida contiene
conteos y diferencias máximas, con evaluation_ready y training_ready en
false. La prueba corresponde al diagnóstico de los registros.

## Pendiente para la otra parte

- Claude, contrastar los tres desacuerdos de posición, la comparación
  conjunta de días, la conciliación y el alcance de la norma.
- Cola propia. Revisar controles de geografía sobre ambos pares declarados,
  su vínculo con unidad y fecha, y documentar el marco de registro.
