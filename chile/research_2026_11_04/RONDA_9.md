# Ronda 9 · Cobertura de la unidad candidata

5 de noviembre de 2026, Santiago. Respuesta a Claude ronda 8, comentario
6651658944 sobre b275340. Reexporté los anexos IFOP después de comprobar los
ZIP y la identidad de los Access extraídos. La comparación CHL reproduce
el cálculo sobre el agregado publicado en 74153bb. Claude revisó código
y agregados IFOP sin acceso a los originales.

## #35 · PARCIAL · Acuerdo sobre el escalado

Confirmo el acuerdo propuesto por Claude. HHMM sigue como hipótesis de
trabajo. Centésimas de hora y registros mixtos quedan abiertos hasta
documentar la regla de origen. Los 36 desbordes de 9154 filas numéricas
(0,39 %) y las frecuencias de valores completos permanecen en la ronda 8.
Queda cerrado el desacuerdo sobre el descarte de E y se retira esa acción
pendiente para Randy. La unidad y el significado de los códigos siguen
pendientes en #35.

## #29 · CERRADO el tratamiento de inclusión D en A

Confirmo la aceptación mutua para claves comparables, con ambas duraciones
residuales positivas y posición, duración y umbral iguales. El caso 75
queda fuera de D. El cierre corresponde a la inclusión matemática y
conserva la sensibilidad de navegación y la unidad sin validar.

## #36 · PARCIAL · Sensibilidad de calendario

En 3122 de 3132 claves el día registrado de zarpe y recalada coincide.
La coincidencia de lance con recalada en 3128 claves sigue siendo un
hecho de los campos. La copia o asignación por defecto es una hipótesis
sobre el mecanismo de registro. Los histogramas completos de 24 horas
están en el JSON.

| Temporada y arte | Moda de zarpe | Moda de recalada | Zarpes en horas 04–05 | Mismo día registrado |
|---|---:|---:|---:|---:|
| 2025 enmalle | 05 | 09 | 440/476 | 474/476 |
| 2025 espinel | 05 | 09 | 1226/1253 | 1251/1253 |
| 2024 enmalle | 04 | 09 | 827/875 | 870/875 |
| 2024 espinel | 04 | 09 | 506/528 | 527/528 |

El patrón es compatible con la hipótesis de reloj local bajo el supuesto
de horario de faena propuesto. La distribución por sí sola deja el huso
abierto. La sección II.5.3 del QUID documenta que el día de GlobColour
corresponde aproximadamente al intervalo UTC de esa fecha. Su definición
resuelve el lado del producto. Sigue pendiente el origen del reloj IFOP.
[QUID, versión 7.0](https://documentation.marine.copernicus.eu/QUID/CMEMS-OC-QUID-009-101to104-111-113-116-118.pdf).

Acepto separar el diagnóstico de día registrado y el de hora de pesca.
Las 3122 claves de día común pueden entrar en sensibilidades agregadas de
calendario con etiqueta de huso sin validar. Las diez restantes conservan
ambos días. El emparejamiento certificado sigue sujeto a #6/#25/#36.

## #25 · PARCIAL · Cobertura observada y especies registradas

| Temporada y arte | Claves | Filas | Claves con otra especie positiva | Filas de otras especies positivas | Meses con claves |
|---|---:|---:|---:|---:|---:|
| 2025 enmalle | 476 | 551 | 63 | 80 | 11 |
| 2025 espinel | 1253 | 1405 | 128 | 154 | 11 |
| 2024 enmalle | 875 | 1049 | 131 | 184 | 11 |
| 2024 espinel | 528 | 610 | 84 | 94 | 9 |
| Total | 3132 | 3615 | 406 | 512 | — |

Las frecuencias de una a cinco filas por clave son 2748, 294, 84, 3 y 3.
Las otras especies excluyen los códigos 1 y 999. Su registro confirma
presencia documental en parte del inventario. Sigue por verificar si
se registraron todas las especies y cantidades de cada faena. La única
fila de merluza permite conservar un PESO reportado por clave. Su alcance
como total de viaje, incluidas las claves con varias caladas, sigue abierto.

Los meses se asignan por recalada registrada y el JSON desglosa días con
claves y estados. Septiembre carece de claves en los cuatro estratos.
Espinel 2024 carece además de julio y agosto. Esto delimita la cobertura
del extracto y deja pendiente el esfuerzo real en esos meses y el marco
muestral. El escenario hipotético de 103 ceros depende de la semántica
de 999 y de excluir las 30 claves sin fila de merluza y el conflicto.
La dirección y magnitud de un sesgo poblacional requieren esas condiciones.

## #17 y #37 · PARCIAL · Gradiente por longitud

Reproduje las medianas por columna en las 118 celdas de soporte fijo L4
con cero muestras de tierra GLOBE. Los rangos son 458,5–473 días en
columnas 0–4, 481,5–489 en 5–6 y 507–516,5 en 7–11. Las diez mixtas
tienen mediana 529,5 frente a 479 en las 118. La celda de referencia tiene
124 celdas por debajo y tres por encima. Es un contraste descriptivo por
longitud. Quedan abiertas la distancia real a costa y las causas físicas
o de procesamiento del patrón.

El contrato exige registrar la fracción del peso espacial aportado por
celdas mixtas y comparar cobertura elegible con y sin ellas cuando haya
soporte. En una asignación a una celda la fracción es 0 o 1. La pérdida
de soporte se conserva como dato del diagnóstico. GLOBE clasifica las
16 celdas sin L4 con centros en tierra y una de ellas tiene muestras
mixtas. El soporte 128 es empírico y la máscara marina independiente
para el emparejamiento sigue pendiente.

## Reproducción y dictamen

```bash
python chile/audit_candidate_coverage.py --raw-dir /ruta/privada/gestion_publica --cell-support chile/research_2026_11_04/arco_cell_support.json --output /ruta/privada/candidate_coverage_audit.json
python -m py_compile chile/audit_candidate_coverage.py
```

Verifiqué conservación de filas, claves, histogramas y conteos mensuales.
Los resultados son agregados. evaluation_ready y training_ready quedan
en false. El dictamen sigue siendo viable condicionado para explorar
rendimiento nominal por clave y arte, sujeto a unidad, fecha, posición,
cobertura y permisos. Los demás estados se conservan.

## Pendiente para la otra parte

- Claude, contrastar el alcance de la sensibilidad de día registrado, el
  gradiente por longitud y el registro de especies en el extracto.
- Cola propia. Contrastar procedencia espacial y marco muestral con las
  fuentes accesibles y preparar una prueba de emparejamiento con anclas
  defendibles.
