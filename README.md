# PredictaMAR Litoral (Pucusana)

Pipeline litoral del proyecto PROCIENCIA E072-2026-01. No reutiliza el código
de PredictaMAR Costero (Chorrillos): incorpora sus aprendizajes y los hallazgos
de la auditoría de agosto de 2026 como contratos verificables.

## Dónde estamos en la secuencia

1. ✅ **Especificación de variables** — `config/variables_spec.yaml`
2. ✅ **Área operativa** — `config/area.yaml`
3. ✅ **Entorno técnico** — dependencias declaradas en `requirements.txt`
4. ✅ **Seis fuentes base** — SST de modelo, salinidad, oleaje, clorofila,
   corrientes superficiales y batimetría, todas con suites sintéticas
5. 🟡 **Primer bloque espacial** — SST observada OSTIA y gradiente térmico
   implementados y validados sintéticamente; diagnóstico real pendiente
6. 🟡 **Validación** — inspector seguro de esquema IMARPE disponible; los datos
   reales restringidos no se almacenan ni se abren en Codespaces
7. 🔲 **Ensamblador y aplicación** — siguientes etapas después de cerrar las
   señales ambientales priorizadas
8. 🔲 **Motor de puntaje** — deliberadamente inactivo hasta validación
   independiente; ninguna variable tiene `predictively_valid: true`

Regresión sintética actual: **185 pruebas**.

## Fuentes y credenciales

1. **Copernicus Marine Service** — https://data.marine.copernicus.eu
   Crear cuenta gratuita. Cubre: SST de modelo, OSTIA, corrientes, estructura
   térmica vertical, salinidad, oleaje y clorofila.
   Instalar el cliente: `pip install copernicusmarine`

2. **GEBCO / CEDA** — la batimetría GEBCO 2026 se consulta por OPeNDAP y no
   depende de Google Earth Engine.

3. **Google Earth Engine y otras fuentes** — permanecen instaladas como
   candidatas para desarrollos futuros; no forman parte del bloque OSTIA.
   Ningún JSON de credenciales ni dato restringido debe subirse al repositorio.

## Principios de diseño que el pipeline aplica

Estos vienen directamente de la auditoría a Costero v1.2 (ago 2026) — no son
opcionales, son la razón de ser de este pipeline nuevo:

- **Checklist de 4 propiedades por variable** (disponible / varía en tiempo /
  varía en espacio / predictivamente válida) — declarado en `variables_spec.yaml`,
  no descubierto después.
- **Fail-safe, no fail-open** — ver `fetch_waves.py`: ante falta de dato, el
  sistema declara `sin_datos` explícitamente, nunca un valor por defecto
  disfrazado de lectura real.
- **Trazabilidad de fuente real** — cada lectura y derivada conserva dataset,
  variable, timestamp, celda o campo, unidades, método y limitación de alcance.
- **Sin redistribución automática de pesos** — pendiente de implementar en
  `scoring/`, pero ya documentado como regla: si falla una capa dinámica, no
  se transfiere su peso en silencio a las capas estáticas.
- **Separación entre verificación técnica y validez predictiva** — que un
  módulo pase sus pruebas no demuestra que encuentre pesca. La admisión al
  scoring exige validación independiente y control de circularidad.

## Siguiente paso inmediato

Ejecutar el diagnóstico real costero del bloque OSTIA + gradiente térmico sin
activar scoring. Requiere una sesión válida de Copernicus Marine y consulta,
por defecto, siete fechas hasta el día anterior en un recuadro técnico alrededor
de Pucusana:

```bash
python -m diagnostics.diagnose_ostia_pucusana
```

Para emitir el mismo resumen como JSON, sin guardar las matrices crudas:

```bash
python -m diagnostics.diagnose_ostia_pucusana --json
```

El recuadro del diagnóstico no representa el alcance operativo de 0–10 km y la
salida no valida pesca ni detecta cardúmenes. Después se evaluará el bloque
vertical `temperature_10m` + `delta_sst_t10`; al cerrar esas señales se
construirá el ensamblador y la aplicación web.
