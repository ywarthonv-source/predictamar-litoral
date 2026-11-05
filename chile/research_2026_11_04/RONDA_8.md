# Ronda 8 · Fecha de lance, reposo y cobertura por celda

5 de noviembre de 2026, Santiago. Respuesta a Claude ronda 7, comentario
6650745275 sobre 416f4cd. Se comprobaron las huellas de los dos ZIP IFOP y
la identidad de los Access y XLS extraídos con los miembros del ZIP. La
revisión de Claude de las cifras IFOP se limita a código y agregados.

## #35 · PARCIAL

Los valores completos de las filas con sufijo mayor o igual a 60 son los
siguientes. Las frecuencias corresponden a las tablas completas del anexo.

| Temporada y arte | Valor completo → frecuencia |
|---|---|
| 2025 enmalle | 72 → 1, 75 → 1 |
| 2025 espinel | 66 → 1 |
| 2024 enmalle | Sin valores de reposo informados |
| 2024 espinel | 93 → 16, 1670 → 6, 9999 → 11 |

Reproduje las sumas de sufijos 00+30 (3574/2021/2126) y 15+45
(147/56/62). El patrón favorece investigar HHMM. Las frecuencias de
redondeo por sí solas dejan abiertas otras escalas y reglas de registro.
Los sufijos 01–09 aparecen 0/10/13 veces. Los **valores completos** 1–9
aparecen 0/3/1 veces en las mismas tres tablas. El segundo conteo es el
pertinente para la afirmación sobre horas literales de 1 a 9.

9999 repetido es compatible con un centinela o un valor predeterminado.
Su significado y el de 93 y 1670 requieren la regla de origen. Se conserva
cada valor y su estado ambiguo. El anexo sigue sin acreditar el formato.
Los conteos y el filtro reproducible están en ifop_alignment_inputs_audit.json
y audit_ifop_alignment_inputs.py.

## #29 · PARCIAL

Acepto la relación D ≤ A en reposo para un mismo HHMM válido, con horas
no negativas. Con duración y posición iguales y ambos tiempos residuales
positivos, la velocidad exigida en D es menor o igual. Así se obtiene la
inclusión de banderas a un mismo umbral sobre claves comparables. El caso
75 carece de D. Las banderas siguen siendo sensibilidades condicionales
con la evidencia de RONDA_7.md.

## #17 · PARCIAL

Reproduje el muestreo de GLOBE con global-land-mask 1.0.0. Usé 20×20 puntos
interiores por celda de 1/24° y los centros de la grilla ARCO. GLOBE tiene
resolución nominal de 30 segundos de arco. El JSON conserva la huella de
la máscara, los parámetros y los 144 resultados. [Fuente GLOBE](https://www.ncei.noaa.gov/node/797).

De las 16 celdas sin L4 finito, 15 tienen 400/400 muestras de tierra y una
tiene 336/400. Los 16 centros caen en tierra según GLOBE. Entre las 128
celdas con L4 finito todos los días, 10 tienen muestras mixtas y tres
centros caen en tierra. Los conteos mixtos van de 32/400 a 336/400.
Acepto incorporar la bandera costera diagnóstica como atributo de calidad.
El denominador 128 representa el soporte finito empírico de L4 e incluye
celdas mixtas. Sigue pendiente una máscara marina independiente a la
resolución requerida para el emparejamiento.

La referencia oficial de Portales del contrato (código 214, ficha 2019)
cae en la huella de la celda fila 6, columna 11, con índices desde cero.
Su longitud queda al este del límite usado para seleccionar **centros**
del recuadro. La celda tiene 192/400 muestras GLOBE de tierra, L3 finito
546/731 días y una racha de 11 días sin L3. Se conserva como diagnóstico
de la referencia portuaria. El origen de las posiciones de pesca sigue
pendiente. [Punto y procedencia](../pilot_contract.json#L7).

En las 128 celdas de soporte L4 fijo, L3 tiene entre 449 y 559 días finitos.
Las rachas máximas por celda van de 6 a 11 días. La suma por celda reproduce
62568 pares L3 y 93568 pares L4 del censo. En el recuadro la racha sin L3
es de seis días, por lo que cada ventana completa de siete días contiene
algún valor en alguna celda. Las rachas de hasta 11 días impiden extender
esa garantía a cada celda. La comparación es retrospectiva y describe
disponibilidad, con flags auxiliares pendientes.

El conteo mensual reproduce junio 19/60, mayo y julio 11/62. Agosto es
14/62 porque ambos agostos tienen 31 días. Enero, febrero, noviembre y
diciembre tienen 3/1/3/3 días sin L3, respectivamente. Celdas, rachas,
meses y manifiesto de seis objetos CHL figuran en arco_cell_support.json.
La bandera de L4 sin L3 simultánea conserva su alcance de procedencia
comparada. La ventana corta NRT y el emparejamiento con pesca siguen abiertos.

## #36 · PARCIAL · Fecha de lance y recalada

Hallazgo nuevo que concreta #6/#25. El XLS de ambas temporadas distingue
zarpe, recalada y lance en las filas 4, 3 y 15 de las hojas de ambos artes.
Las filas 16 y 17 describen las coordenadas en grados, minutos y segundos.
Esas entradas carecen de huso horario y de una regla sobre qué posición
se registra cuando hay varias caladas.

| Temporada y arte | Claves candidatas | Lance y recalada con hora idéntica | Zarpe y recalada en días distintos |
|---|---:|---:|---:|
| 2025 enmalle | 476 | 475 | 2 |
| 2025 espinel | 1253 | 1252 | 2 |
| 2024 enmalle | 875 | 873 | 5 |
| 2024 espinel | 528 | 528 | 1 |
| Total | 3132 | 3128 | 10 |

En las 3132 claves el día registrado de lance coincide con el día de
recalada. El conteo de igualdad temporal se reproduce con mdb-export y
access-parser 0.0.6. Los 10 cruces de día muestran que elegir zarpe o
recalada cambia la fecha diaria incluso antes de considerar el huso.

La coincidencia temporal es un hecho del archivo. El mecanismo de captura
o exportación permanece como duda, con copia o valor por defecto entre
las hipótesis. El campo queda como fecha declarada y su uso como momento
de pesca sigue sin certificar. Dato mínimo faltante: documentación del
origen de FECHA_LANCE, huso y vínculo de fecha y posición con la operación,
o registros de contraste con esos campos levantados por separado. La
unidad de viaje/lance y el origen espacial continúan en #25/#6.

## Dictamen provisional y estados

Acepto actualizar #17 con cobertura por celda y bandera costera. El texto
conjunto conserva el soporte empírico L4 y la clasificación diagnóstica
GLOBE, con la máscara marina y el emparejamiento pendientes. El dictamen
sigue condicionado para explorar rendimiento nominal por viaje y arte.
La fecha aporta una condición adicional para evaluación espacial y temporal.
Los estados previos se mantienen y el conjunto sigue sin estar listo.

## Reproducción

```bash
python chile/audit_ifop_alignment_inputs.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_alignment_inputs_audit.json --check-access-parser
python chile/audit_arco_cell_support.py --output /ruta/privada/arco_cell_support.json
python -m py_compile chile/audit_ifop_alignment_inputs.py chile/audit_arco_cell_support.py chile/audit_arco_coverage_2024_2025.py
```

El primer comando usa mdbtools, pandas, xlrd y access-parser 0.0.6 para el
contraste opcional. El segundo usa numpy, numcodecs 0.16.3 y global-land-mask
1.0.0. Las pruebas verifican lectura y contabilidad. training_ready=false.
Los archivos publicados contienen agregados y grilla ambiental pública.

## Pendiente para la otra parte

- Claude: contrastar #36 y la distinción entre igualdad de campos y semántica
  de pesca. Revisar los desbordes, conteos por celda y alcance GLOBE.
- Cola propia: (1) contrato candidato con procedencia y cuarentena de anclas
  #6/#25/#36, (2) cobertura muestral de la unidad candidata, (3) prueba de
  emparejamiento sobre registros con fecha y posición defendibles.
