# Captura declarada y evidencia interna de faena

4 de noviembre de 2026, Santiago. Evidencia para la respuesta de la ronda 4.
Alcance: tablas públicas artesanales IFOP 2024/2025, Portales=560 y especie
objetivo merluza=1. No se corrigieron ni eliminaron los originales.

## Estados registrados por clave candidata de viaje

| Temporada/arte | Merluza positiva | Merluza con peso cero | Solo código 999 con peso cero | Merluza no listada: sin imputar cero | Código 999 con peso positivo |
|---|---:|---:|---:|---:|---:|
| 2025 enmalle | 454 | 0 | 17 | 5 | 0 |
| 2025 espinel | 1.225 | 2 | 23 | 3 | 0 |
| 2024 enmalle | 820 | 12 | 33 | 10 | 0 |
| 2024 espinel | 499 | 6 | 10 | 12 | 1 |

Los estados son mutuamente excluyentes bajo el algoritmo documentado. Suman
3.132 claves candidatas: 2.998 positivas, 20 con merluza en cero, 83 solo
código 999 y peso cero, 30 sin fila de merluza y un conflicto de etiqueta/peso.
No hay coincidencias de la clave candidata entre artes dentro de cada año.
Esto comprueba la contabilidad de estos archivos; no certifica independencia
estadística ni cobertura completa de la flota.

## Evidencia de faena declarada en los 103 candidatos de peso cero

Los 20 casos con merluza en cero y los 83 de código 999/peso cero tienen:
- esfuerzo declarado positivo en todas sus filas;
- N_CALADAS positivo en todas sus filas;
- zarpe, recalada y lance parseables, duración de viaje positiva y lance dentro
  del intervalo zarpe-recalada.

En 58 de esas claves el valor de reposo declarado es positivo; en 45 falta
(todos los candidatos de enmalle 2024). No se convierten faltantes en cero.
Actualización de ronda 5: toda la tabla de enmalle 2024 carece de reposo, no
solo estos ceros. El valor positivo no se valida como duración dentro del viaje:
en los 2.255 candidatos con reposo informado de las otras tablas supera las
horas zarpe-recalada bajo la unidad literal del diccionario. Véanse #34/#35 en
RONDA_5.md antes de interpretarlo o restarlo del tiempo disponible.
Los cuatro campos de inicio/fin de calado y virado están vacíos en todos los
candidatos de peso cero. También están vacíos en las filas positivas examinadas:
no existe aquí un registro temporal independiente de despliegue/recogida.

Estos campos aportan coherencia interna y hacen plausible una faena declarada,
pero no demuestran por sí solos faena observada ni ausencia ecológica de peces.
El significado del código 999 no se resuelve solo por esos campos: el maestro
lo denomina viaje sin captura y contiene también la etiqueta Sin movimiento.
El conflicto de peso positivo de #27 se mantiene separado.

## Documentación metodológica recuperada

Se descargó el informe público de gestión 2025, Sección I. Sus páginas PDF 18,
24 y 29 describen encuestas artesanales en desembarque y algunos embarques,
la incorporación de viajes sin pesca cuando pudieron obtenerse, y posiciones
provenientes de dirección/distancia desde costa o GPS de observadores a bordo.
No se documenta en esos pasajes cómo distinguir el origen posicional de cada
fila ni la exhaustividad de los ceros en Portales.

Fuente y SHA-256: gestion_2025_methodology_source.json. Esta documentación
refuerza la cautela espacial de #6: coordenadas con formato sexagesimal no
garantizan precisión de GPS. Esos pasajes tampoco prueban que cada registro
de código 999 haya sido observado directamente en el mar.

## Objetivo candidato, sin modelo ni etiquetas validadas

La vía más defendible para examinar con estos archivos es el rendimiento
nominal registrado por viaje muestreado, separado por arte. No se presenta
como predicción de biomasa o presencia real de cardúmenes. Antes de tratarlo
como conjunto evaluable deben aceptarse las reglas de unidad, peso/esfuerzo,
ceros, precisión posicional, muestreo y condiciones de reutilización.

Los candidatos de cero se conservarán separados por su procedencia, los 30
sin fila de merluza seguirán sin etiqueta inferida y el conflicto de #27 no
se resolverá automáticamente. No se calculó CPUE ni se entrenó un modelo.
El alcance de artes del piloto sigue pendiente de la decisión de Randy;
estos son estratos exploratorios de datos, no una selección operativa.

## Reproducción y pendiente

```bash
python chile/audit_ifop_zero_activity.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_zero_activity_audit.json
```

El script se ejecutó sobre las cuatro tablas y compiló. Comprueba el SHA-256
de los originales y mantiene zero_labels_validated=false y training_ready=false.
Los resultados agregados están en ifop_zero_activity_audit.json. Ningún
identificador individual ni fila original se publica.

Claude: reproducir estados y actividad declarada; contrastar esta interpretación
de #6/#25 y el objetivo candidato. Próximos pasos propios: disponibilidad de
origen/precisión posicional, cobertura del muestreo y diseño de evaluación
agrupado por embarcación/tiempo, sin ajustar modelos. La solicitud institucional
2026-122 sigue ingresada; no se requiere que Randy repita ninguna gestión.

