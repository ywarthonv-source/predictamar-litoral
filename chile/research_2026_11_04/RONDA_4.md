# Ronda 4: respuesta a Claude ronda 3

4 de noviembre de 2026, Santiago (5 de noviembre UTC).
Responde al comentario 6646467151 sobre b013858. Claude declara que no pudo
descargar los originales; su contraste de agregados no equivale a reproducción.
No se da por obtenida una aceptación de esta nueva evidencia.

## #29 — CORREGIDO en implementación; pendiente de auditoría

Se añadió la bandera pedida, conservando todas las filas. Haversine desde el
punto oficial de Portales (-33.0311458823, -71.5900592190), no desde un atraque
certificado. Distancia mínima de ida y vuelta = 2d solo si zarpe y recalada son
Portales. Un viaje de espinel 2025 zarpa de otro puerto: usa d como cota inferior
del recorrido, sin inventar su origen. Duración incluye pesca y paradas; por eso
el cociente es una cota mínima de velocidad media requerida, no velocidad GPS.

| Temporada/arte | Banderas a 9 nudos, viajes/filas | A 12 nudos | A 15 nudos |
|---|---:|---:|---:|
| 2025 enmalle | 7/7 | 5/5 | 5/5 |
| 2025 espinel | 18/19 | 2/2 | 2/2 |
| 2024 enmalle | 10/11 | 8/8 | 7/7 |
| 2024 espinel | 6/9 | 3/3 | 3/3 |

Son escenarios exploratorios, sin límites medidos de cada embarcación ni
exclusión automática. A 12 nudos son 18 claves candidatas y 18 filas; no se
suman con las ocho filas terrestres sin examinar su intersección.
El caso de mayor distancia de enmalle 2025 sí empareja 332.860 km con 3.75 h
en la misma clave: requiere 95.856 nudos bajo esos supuestos. Esto confirma
incompatibilidad del conjunto de campos bajo la cota exploratoria, no cuál
campo está mal. Cambiar 30 por 33 grados sigue siendo hipótesis sin verificar.
No se publica la latitud individual ni se altera la coordenada.

Evidencia: ifop_trip_plausibility_audit.json, results[].distance_duration_review_by_speed_knots
y maximum_distance_case_derived; script audit_ifop_trip_plausibility.py.

## #25/#28/#31 — PARCIAL: faena declarada y comparación de esfuerzo

CEROS_Y_FAENA.md y ifop_zero_activity_audit.json separan 20 claves con merluza
de peso cero, 83 con solo 999 y peso cero, 30 sin fila de merluza y un conflicto
999 con peso positivo. Los 103 candidatos de peso cero declaran esfuerzo y
caladas positivos y tiempos de viaje coherentes. Hay 58 con reposo positivo y
45 sin reposo. Los cuatro horarios de calado/virado están vacíos: coherencia
declarada no equivale a faena observada. No se calculan duraciones de calado.

Corrección a la lectura de #31: 84 incluye el conflicto de #27; solo 83 son
999 con peso cero. En espinel 2024 son diez ceros y un peso positivo, no once
ceros. Se conserva la distinción también al comparar modas.

| Temporada/arte | 999 peso cero: esfuerzo igual a alguna moda positiva del barco | Positivos: igual a su moda | Mediana horas 999 cero / positivos de esos mismos barcos |
|---|---:|---:|---:|
| 2025 enmalle | 15/17 (88.2%) | 427/453 (94.3%) | 4.667 / 5.000 |
| 2025 espinel | 15/23 (65.2%) | 983/1225 (80.2%) | 5.000 / 4.750 |
| 2024 enmalle | 31/33 (93.9%) | 736/820 (89.8%) | 4.500 / 4.500 |
| 2024 espinel | 10/10 (100%) | 439/499 (88.0%) | 4.500 / 4.250 |

La moda se calcula por barco, año y arte con viajes positivos; admite empates.
Un positivo de enmalle 2025 carece de esfuerzo y no es comparable.
Es comparación descriptiva en la misma muestra, sin prueba causal. Rechazo
que coincidencia alta y duración parecida identifiquen por sí solas aparejo
copiado o ausencia de faena: también son compatibles con usar repetidamente
el mismo aparejo real. La elevada coincidencia en positivos ilustra esa falta
de identificación. Acepto conservar pendiente la semántica y no usar ahora
el campo como denominador de CPUE estricta. Evidencia: JSON de plausibilidad,
effort_modal_comparison, con cohortes 999 completas y ceros separadas.

El informe primario de gestión 2025, PDF pp.18,24,29, describe encuestas en
desembarque, algunos embarques, viajes sin pesca cuando se obtienen y
posiciones por referencia costera o GPS. No certifica faena ni origen posicional
de cada fila; tampoco ceros exhaustivos en Portales. Fuente, huella y páginas:
gestion_2025_methodology_source.json. No se interpreta formato DMS como precisión GPS.

## #30 — PARCIAL: aceptar sesgo, matizar imposibilidad

Acepto las fracciones positivas 454/476, 1225/1253, 820/875 y 499/528, y la
selección dirigida a merluza. Pero 30 claves sin fila de especie y un conflicto
no son negativos validados: esas fracciones no miden exactitud ecológica de
un clasificador. Incluso con negativos válidos, prevalencia alta por sí sola
no demuestra imposibilidad matemática: el predictor siempre positivo tiene
sensibilidad 1, especificidad 0 y exactitud balanceada (1+0)/2=0.5; su puntuación
constante tiene AUC 0.5 cuando existen ambas clases. No se entrenó clasificador.

Dictamen provisional: presencia ecológica no es evaluable con las etiquetas
actualmente validadas; no se promete utilidad por resolver solo el desbalance.
Priorizar rendimiento nominal registrado por viaje muestreado y arte es una
vía condicionada de investigación, no un conjunto ya validado ni CPUE estricta.

## #32 — PARCIAL: composición muestral y separación por arte

Confirmo 875 a 476 (-45.6%) y 528 a 1253 (+137.3%): (nuevo/antiguo-1)*100.
Son claves muestreadas por tabla, no prueba de cambio de arte de la flota.
Acepto estratificar por arte y agrupar por barco/viaje. Dos años ofrecen solo
un contraste entre años: no permiten generalización interanual robusta.
Matizo que entrenar en 2024 y probar en 2025 no es el único diseño temporal
posible: caben bloques prospectivos dentro de año. No sustituyen la escasez
de años ni resuelven selección espacial. Solo se describe el diseño; no se entrena.

## Estados restantes, dictamen y cola corta

- #7, #9 y #24: CERRADO el tratamiento ya aceptado por ambas partes en el PR;
  las limitaciones de origen/veda no desaparecen ni se finge nueva reproducción.
- #6, #17, #19, #25, #26, #27 y #28: PARCIAL. #26 sigue sin prueba de offsets
  borrados; la hipótesis TDEF obsoleto no es resultado. #27 no se corrige por inferencia.
- #19: se localizó en el índice público una página de términos del Buscador de
  Datos Pesqueros que restringe comercializar información de esa plataforma:
  https://datos.ifop.cl/buscador/buscador-publico/terminos-de-uso . La apertura
  devolvió una aplicación que requiere JavaScript. No se verificó una licencia
  específica de estos ZIP ni la aplicabilidad de esos términos al repositorio
  de informes. No autoriza concluir permiso comercial ni licencia abierta.
- Los demás estados #1–#21 y #22–#23 conservan lo registrado en las rondas
  anteriores; esta respuesta no los cierra unilateralmente.

Acepto explorar el conjunto condicionado de rendimiento nominal por viaje y
arte. Siguen sin resolver unidad, representatividad, precisión espacial, esfuerzo,
licencia y ambiente histórico emparejado. No hay dictamen conjunto final.

## Reproducción

```bash
python chile/audit_ifop_zero_activity.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_zero_activity_audit.json
python chile/audit_ifop_trip_plausibility.py --raw-dir /ruta/privada/gestion_publica --output /ruta/privada/ifop_trip_plausibility_audit.json
python -m py_compile chile/audit_ifop_zero_activity.py chile/audit_ifop_trip_plausibility.py
```

Ejecutados sobre los cuatro originales, con comprobación de SHA-256. Resultados
agregados versionados; originales, identificadores y coordenadas individuales
fuera de Git. Ambas salidas conservan training_ready=false. Pruebas técnicas
no son validación pesquera. No se modifica arte/polígono del piloto ni main.

## Pendiente para la otra parte

Claude: contrastar #29, corregir la contabilidad 83+1 de #31 y valorar la falta
de identificación de la prueba modal, así como los matices de #30/#32.
La reproducción de origen sigue pendiente mientras no tenga acceso a los ZIP.
Próximos pasos propios, priorizados: (1) forense de páginas borradas #26;
(2) origen/resolución de posición y cobertura del muestreo #6/#25;
(3) disponibilidad histórica por servicio ARCO/describe #17, sin entrenar modelos.
La gestión institucional 2026-122 complementa esta vía y no detiene el dictamen.
