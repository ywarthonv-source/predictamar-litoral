# PredictaMAR Litoral (Pucusana) — desde cero

Este es el punto de partida real del nuevo pipeline para el proyecto PROCIENCIA
E072-2026-01. No reutiliza el código de PredictaMAR Costero (Chorrillos) —
lo usa como aprendizaje, no como plantilla, incorporando los hallazgos de la
auditoría de agosto 2026 desde el diseño, no como parches posteriores.

## Dónde estamos en la secuencia

1. ✅ **Especificación de variables** — `config/variables_spec.yaml`
2. ✅ **Área operativa** — `config/area.yaml`
3. 🔲 **Entorno técnico** — pendiente: crear cuentas y credenciales (ver abajo)
4. 🔲 **Ingesta de datos** — esqueletos listos (`ingestion/fetch_chlorophyll.py`,
   `ingestion/fetch_waves.py`), faltan las llamadas reales a las APIs y el
   resto de las variables (SST, corrientes, gradiente, salinidad, radar,
   batimetría, zonas empíricas, viento)
5. 🔲 **Motor de puntaje** — no empezado (carpeta `scoring/`)
6. 🔲 **Validación** — no empezado (carpeta `validation/`)
7. 🔲 **Despliegue** — no empezado

## Cuentas y credenciales que necesitas crear (paso 3)

1. **Copernicus Marine Service** — https://data.marine.copernicus.eu
   Crear cuenta gratuita. Cubre: SST, corrientes, gradiente vertical,
   salinidad, oleaje, y clorofila (ambos productos, 300m y 4km).
   Instalar el cliente: `pip install copernicusmarine`

2. **Google Earth Engine** — https://earthengine.google.com
   Necesario para: radar (Sentinel-1), batimetría (GEBCO vía GEE), y como
   alternativa de acceso a Sentinel-3/OLCI si el catálogo de Copernicus
   Marine no cubre algún caso puntual.
   Para automatizar (GitHub Actions): crear una cuenta de servicio y
   descargar el JSON de credenciales — NUNCA subir ese archivo al repo.

3. **ALOS-2** — el acceso suele requerir solicitud a JAXA o un proveedor
   comercial; queda pendiente de decidir si se incluye desde el arranque o
   se deja como mejora futura (a diferencia de Sentinel-1, que es de acceso
   abierto inmediato).

## Principios de diseño que este esqueleto ya aplica

Estos vienen directamente de la auditoría a Costero v1.2 (ago 2026) — no son
opcionales, son la razón de ser de este pipeline nuevo:

- **Checklist de 4 propiedades por variable** (disponible / varía en tiempo /
  varía en espacio / predictivamente válida) — declarado en `variables_spec.yaml`,
  no descubierto después.
- **Fail-safe, no fail-open** — ver `fetch_waves.py`: ante falta de dato, el
  sistema declara `sin_datos` explícitamente, nunca un valor por defecto
  disfrazado de lectura real.
- **Trazabilidad de fuente real** — ver `fetch_chlorophyll.py`: cuando una
  variable tiene más de una fuente posible (300m vs 4km), el sistema siempre
  reporta cuál se usó, no solo el valor final.
- **Sin redistribución automática de pesos** — pendiente de implementar en
  `scoring/`, pero ya documentado como regla: si falla una capa dinámica, no
  se transfiere su peso en silencio a las capas estáticas.
- **Validación contra el mapa estático, no solo contra IMARPE** — pendiente
  en `validation/`: el modelo completo debe demostrar que supera a
  batimetría + zonas empíricas solas, con puntos de control fuera de esas
  zonas empíricas (evitar validación circular).

## Siguiente paso inmediato

Configurar las credenciales de Copernicus Marine y completar
`fetch_chlorophyll.py` / `fetch_waves.py` con las llamadas reales, usando esos
dos archivos como plantilla para las demás variables de `variables_spec.yaml`.
