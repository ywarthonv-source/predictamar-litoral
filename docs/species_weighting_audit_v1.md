# Auditoría y rediseño de ponderación por especie — v1

Fecha de corte: 2026-09-07
Rama: `feat/species-weighting-v1`
Estado: matriz objetivo de investigación; **no validada predictivamente y no operativa**

## Decisión

La tabla histórica de `SPECIES_RULES` se recuperó completa, pero **no es
correcto trasladarla al ensamblador Litoral**. Sirve como antecedente, no como
modelo vigente. La copia inmutable para auditoría está en
`config/legacy_species_rules_v0.yaml`; la nueva hipótesis trazable está en
`config/species_weighting_v1.yaml`.

La salida futura se denomina **Índice experimental de compatibilidad
ambiental**. No es probabilidad de encontrar o capturar pescado, no incluye
semaforización y no puede ordenar puntos con datos incompletos.

## Correcciones de la segunda auditoría

La revisión adversarial posterior no cambió las especies ni sus pesos
provisionales. Cerró cuatro huecos de contrato antes de cualquier fusión:

1. El validador fija el estado de investigación, `catch_prediction: false`,
   las prohibiciones de faltantes y el peso cero del oleaje.
2. Ningún `factor_score` escalar o autodeclarado es admisible. Cada entrada
   necesita transformación, versión, calibración y versión de fuente que
   coincidan con un registro aprobado. El registro real permanece vacío y
   pendiente, por lo que todavía no puede existir un índice completo.
3. El bundle diario incluye todos sus metadatos críticos en la huella y
   recalcula rango, conteos, bloqueo de scoring, fecha y coordenadas internas.
   La interfaz podrá exigir fecha esperada y edad máxima de generación.
4. El diagnóstico espacial alinea timestamps comunes y compara solo valores
   numéricos con tolerancias explícitas. Su salida admite variables únicamente
   a backtesting; nunca declara que puedan ordenar puntos.

## Por qué la aplicación histórica no rotaba los datos

La aplicación general y el programador quedaron desacoplados:

- `app.py` cargaba las hojas `FEATURES_7D` y `SPECIES_RULES`.
- `pipeline.py` v6.2 publicaba `reporte_diario`, `escala3_v62`,
  `historial_zonas` e `ipo_zonas`.
- El workflow podía finalizar correctamente sin actualizar la tabla que leía
  la pantalla histórica de 2.798 puntos.
- La caché de la aplicación añadía hasta una hora más de persistencia, pero no
  era la causa raíz.

El backend nuevo deberá publicar un manifiesto versionado y la aplicación
deberá rechazar una instantánea cuyo `schema_version`, fecha o identificador de
corrida no coincidan. No se volverán a usar nombres de hojas implícitos.

## Auditoría de la ponderación histórica

El cálculo antiguo era:

```text
score = sum(w_i * componente_i) / sum(w_i)
```

Aunque la tabla aparentaba contener pesos directos, ninguna fila sumaba 1. La
división final cambiaba silenciosamente sus magnitudes:

| Etiqueta histórica | Suma declarada | Factor oculto `1/suma` |
|---|---:|---:|
| ANCHOVETA | 0,93 | 1,0753 |
| CHAUCHILLA | 0,85 | 1,1765 |
| PEJERREY | 0,83 | 1,2048 |
| BONITO | 0,83 | 1,2048 |
| JUREL | 0,79 | 1,2658 |
| CABALLA | 0,77 | 1,2987 |
| POTA | 0,68 | 1,4706 |
| MERLUZA | 0,50 | 2,0000 |
| LORNA | 0,75 | 1,3333 |
| CABINZA | 0,68 | 1,4706 |

Otros problemas que invalidan el traslado directo:

1. Corriente, salinidad y estabilidad de clorofila faltantes se sustituían por
   la mediana del conjunto consultado; frentes y gradientes faltantes, por cero.
2. Los percentiles de clorofila y estabilidad dependían del radio y de los
   puntos incluidos en cada consulta; dos búsquedas no eran comparables.
3. `front_score_7d` ya mezclaba gradientes y algunas especies añadían además
   `grad_chl_pctl`, con riesgo de contar dos veces la misma señal.
4. La batimetría se calculaba, pero no participaba en la tabla de especies; el
   error era especialmente grave para merluza, lorna y cabinza.
5. La magnitud de corriente eliminaba su dirección y no representaba
   convergencia, persistencia ni transporte respecto de la costa.
6. El filtro macro era igual para todas las especies y podía bloquear la
   búsqueda antes del modelo específico.
7. La conversión visual posterior (`30 + score*50`, ajustes por cuatro banderas
   y límites 30–95) era una escala arbitraria. Cambiar su nombre a “índice” no
   la convirtió en una estimación validada.
8. La clorofila histórica de 0,25° —aproximadamente 27 km— no podía discriminar
   el corredor litoral de 0–10 km.
9. La documentación mencionaba doce variables, mientras el score específico
   tenía siete componentes. No existía correspondencia uno a uno verificable.

## Identidad de las especies

Se conservan las diez etiquetas elegidas para la interfaz:

`ANCHOVETA`, `JUREL`, `CABALLA`, `BONITO`, `POTA`, `MERLUZA`, `LORNA`,
`CABINZA`, `CHAUCHILLA` y `PEJERREY`.

Corresponden a **nueve taxa canónicos**. IMARPE registra “Bonito, chauchilla”
bajo `Sarda chiliensis chiliensis`; por tanto, `CHAUCHILLA` es un alias de
`BONITO` y hereda exactamente el mismo modelo. No se permite una fila de pesos
independiente sin evidencia explícita de etapa de vida y una validación propia.

## Correspondencia entre el modelo histórico y las diez variables reales

| Señal histórica | Variable Litoral | Correspondencia | Decisión |
|---|---|---|---|
| `sst_mean_7d` | `sst` + `sst_observed_ostia` | Parcial: modelo PT6H y OSTIA diaria no son la misma magnitud | Un único factor térmico; OSTIA no recibe un segundo peso |
| `chl_mean_7d` | `clorofila` | Parcial: ahora es una lectura diaria L4 de ~4,5 km, no media de 7 días | Transformación absoluta pendiente de calibración |
| `front_score_7d` / `grad_sst_mean_7d` | `thermal_front` | Parcial: el nuevo frente es gradiente OSTIA explícito | Contexto regional; pendiente de colinealidad y validación |
| `sal_mean_7d` | `salinidad` | Parcial: serie nativa PT6H, no media de 7 días | Curva por especie pendiente |
| `curr_mean_7d` | `surface_currents` | Incompleta: el vector existe, pero no persistencia/convergencia | No usar solo rapidez como favorabilidad |
| `chl_cv_7d` | Ninguna | Ausente | No imputar ni sustituir |
| `grad_chl_pctl` | Ninguna | Ausente | No duplicar con el frente térmico |
| Ninguna | `temperature_10m` + `delta_sst_t10` | Nueva señal conjunta | Un factor, no dos; delta no es termoclina |
| Ninguna | `batimetria` | Nueva señal estructural | Usar profundidad/pendiente; TID no es sustrato |
| Ninguna | `oleaje` | Nueva compuerta de seguridad | Peso cero; fuera del índice |

Siete salidas del ensamblador son `point`, `oleaje` es
`regional_maximum`, y OSTIA/frente térmico son `regional_field`. El campo
OSTIA usa semiancho 0,15° como contexto regional; excede el alcance operativo
de 0–10 km y no representa exactamente el área de faena.

## Nueva matriz objetivo

Los pesos se almacenan como enteros en puntos base y cada taxón suma
exactamente 10.000. **Son un prior explícito para organizar la investigación,
no coeficientes estimados por la literatura.** Las fuentes sustentan la
selección de predictores; el valor numérico deberá calibrarse con captura/no
captura o CPUE y validación espacio-temporal fuera de muestra.

| Taxón | Pesos objetivo de mayor magnitud | Vacíos que hoy impiden un índice completo | Encaje 0–10 km Pucusana |
|---|---|---|---|
| Anchoveta | salinidad sup. 23%; temperatura sup. 22%; clorofila 18%; oxígeno sup. 12% | Oxígeno disuelto superficial; transformaciones y datos de campo | Plausible, pendiente de validación local |
| Jurel | frente 22%; temperatura sup. 18%; salinidad 15%; oxígeno subsup. 15% | Oxígeno y temperatura subsuperficial, SLA | Evidencia principalmente oceánica/frontal; escala generalmente incompatible |
| Caballa | temperatura sup. 22%; NPP 22%; SLA 20%; salinidad 10% | NPP y SLA; CHL no se declara sustituto de NPP | Condicional/transzonal, sin validación litoral |
| Bonito / chauchilla | temperatura sup. 22%; presas 22%; frente 15%; transporte 10% | Campo de presas, SLA y modelo local | Condicional/transzonal |
| Pota | NPP 18%; SLA 18%; temperatura sup. 17%; T50 y oxígeno subsup. 16% cada uno | NPP, SLA, T50, oxígeno y presas | Pesquería mayormente oceánica; escala incompatible en general |
| Merluza | oxígeno fondo 30%; temperatura fondo 25%; batimetría 20% | Condición completa de fondo, sustrato y transporte subsuperficial | Pucusana suele quedar fuera del dominio neutro; excepción El Niño |
| Lorna | batimetría 25%; sustrato 22%; oxígeno fondo 14%; temperatura fondo 12% | Sustrato y condiciones de fondo/presas | Costera plausible, pero modelo incompleto |
| Cabinza | sustrato 30%; batimetría 23%; oxígeno fondo 10% | Sustrato y condiciones de fondo/presas | Costera plausible, pero modelo incompleto |
| Pejerrey | temperatura sup. 22%; oxígeno sup. 22%; salinidad/presas 12% cada uno | Oxígeno y campo de presas | Costera plausible, pendiente de validación local |

## Fórmula y tratamiento de faltantes

Para una especie `s` y factores ya transformados a `[0,1]` mediante curvas
versionadas, calibradas y registradas:

```text
I_s = Σ_f (weight_bp[s,f] / 10000) × factor_score[s,f]
```

Reglas obligatorias:

- Cada entrada contiene `value`, `transform_id`, `transform_version`,
  `calibration_id` y `source_data_version`; los cuatro metadatos deben coincidir
  con `transform_registry.approved_transforms`.
- Mientras `transform_registry.status` sea `pending_species_calibration`, se
  rechaza cualquier valor no nulo y no puede emitirse un índice completo.
- El motor no divide por la suma observada ni modifica pesos en ejecución.
- Si falta un factor con peso positivo, `index_value = null` y el estado es
  `insufficient_data`.
- Se informa `coverage_weight` y un intervalo diagnóstico `[lower_bound,
  upper_bound]`; ese intervalo no puede usarse para ranking.
- Cero observado es distinto de dato ausente.
- No existen rangos verde/amarillo/rojo.
- La respuesta contiene `is_probability: false` y
  `operational_enabled: false`.

No se han inventado curvas a partir de rangos publicados. Un rango de
ocurrencia observado no demuestra una función de respuesta, un óptimo ni una
probabilidad. El siguiente paso científico es ajustar esas curvas y los pesos
con observaciones independientes.

## Compatibilidad espacial preliminar

Antes de consultar datos reales, la resolución declarada ya anticipa el límite:

| Variable | Resolución aproximada | Capacidad teórica dentro de 10 km |
|---|---:|---|
| Batimetría | ~0,45 km por eje | Alta para estructura, con límites propios de GEBCO |
| Clorofila | ~4,53 km | Potencial de 2–3 celdas; debe verificarse con datos reales |
| OSTIA / frente | ~6 km | Contexto regional; no lectura puntual del área de faena |
| SST, salinidad, T10, delta, corrientes | ~8,9–9,1 km | Marginal: varios candidatos compartirán celda |
| Oleaje | ~8,9 km | Solo seguridad regional; no ranking |

Por ello, “el producto entrega datos” no basta. El diagnóstico real debe
reportar por variable cuántas celdas y grupos numéricos aparecen en los puntos
operativos aprobados, sobre timestamps comunes y por encima de una tolerancia
declarada. Si una variable no muestra variación comparable, podrá describir el
día, pero no avanzará al backtesting espacial. Incluso si muestra variación,
este diagnóstico no la autoriza a ordenar zonas dentro de 0–10 km.

## Fuentes primarias usadas para estructurar la hipótesis

- IMARPE, *Rangos preferenciales de temperatura y salinidad de la anchoveta
  peruana*: <https://repositorio.imarpe.gob.pe/items/d174722e-3a4c-41d9-949e-9242695dee37>
- Castillo et al. (2022), anchoveta, <https://doi.org/10.1111/fog.12601>
- Dioses (2013), jurel y frente ACF–ASS:
  <https://www.scielo.org.pe/scielo.php?pid=S1727-99332013000100010&script=sci_arttext>
- Torrejón-Magallanes et al. (2021), caballa,
  <https://doi.org/10.1016/j.pocean.2021.102672>
- IMARPE, bonito: <https://www.gob.pe/institucion/imarpe/informes-publicaciones/7266743-informe-correspondiente-al-oficio-n-1712-2025-imarpe-pe>
- IMARPE, “Bonito, chauchilla” bajo el mismo taxón:
  <https://repositorio.imarpe.gob.pe/bitstreams/3435fdd5-f34a-4be4-a865-4dc1e5c0e446/download>
- Yu, Chen y Zhang (2019), pota,
  <https://doi.org/10.1016/j.jmarsys.2019.02.011>
- IMARPE, merluza y oceanografía:
  <https://repositorio.imarpe.gob.pe/items/349fb341-cee6-405f-bd11-b71c19d0b951>
- IMARPE, desplazamiento austral de merluza durante El Niño:
  <https://repositorio.imarpe.gob.pe/items/77d83ba2-c658-4b79-b3a6-a3b9308ef922>
- Atoche-Suclupe et al. (2024), lorna:
  <https://www.scielo.cl/scielo.php?pid=S0718-19572024000300216&script=sci_arttext>
- IMARPE, cabinza:
  <https://repositorio.imarpe.gob.pe/items/b28f2c0d-ca40-4c3c-b5f1-ef7bb537e16a>
- Maldonado Vásquez (2021), pejerrey y calidad de agua en Carquín:
  <https://repositorio.unjfsc.edu.pe/handle/20.500.14067/4809>

## Compuertas para avanzar

1. Aprobar coordenadas/sectores operativos cuya distancia mar adentro esté
   documentada entre 0 y 10 km; no inventar un círculo alrededor de la caleta.
2. Ejecutar el diagnóstico real multípunto con credenciales Copernicus y
   registrar celdas/valores distintos por variable.
3. Incorporar los predictores faltantes que sean técnicamente viables; no usar
   GEBCO TID como sustrato ni CHL como sustituto silencioso de NPP.
4. Definir curvas crudo-a-factor con versión y procedencia.
5. Calibrar pesos con datos independientes IMARPE/captura/CPUE y separación
   temporal y espacial de entrenamiento/prueba.
6. Solo entonces habilitar índices, comparar contra una línea base y conectar
   la aplicación. `main` permanece intacta hasta superar estas compuertas.
