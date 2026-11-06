# Clorofila L3 en la celda de referencia de Portales, 2026

6 de noviembre de 2026. Auditoría del bloque exploratorio SAIP, sin incorporar originales de pesca. Coordenadas de la celda: −33,020835876464844, −71,60416412353516.

## #65 CORREGIDO, pendiente de contraste

Ejecuté `python chile/audit_saip_chl_coverage.py > /tmp/pm46/result.json` con NumPy y numcodecs 0.17.1. El [resultado ambiental](saip_chl_arco_2026.json) conserva los valores diarios, versiones y huellas de las respuestas. La extracción leyó solo la celda de referencia y 666.206 bytes en MY y 617.228 bytes en NRT, incluidas coordenadas y metadatos.

El eje válido MY 202603 fue 1997-09-04 a 2026-10-29. En NRT 202411, los atributos ARCO de tiempo marcan `validStartIndex=750` y `validStartDate=2026-10-20`. El eje leído desde ese índice fue 2026-10-20 a 2026-11-05. La cobertura nominal NRT de la ronda anterior no corresponde a la ventana válida de este servicio.

| Producto | Días ambientales en ventana, finitos / total | Recalada con CHL finita (días / filas) | Recalada sin CHL dentro del eje (días / filas) | Fuera de eje (días / filas) |
|---|---:|---:|---:|---:|
| MY | 197/302 | 122 / 1.751 | 46 / 491 | 3 / 19 |
| NRT | 11/15 | 5 / 63 | 3 / 33 | 163 / 2.165 |

Denominadores pesqueros: 171 días y 2.261 filas de enmalle o espinel, incluida la anomalía solo para este censo ambiental. Se aplicaron los límites y valores de relleno del proveedor. Finitud no equivale a control completo de banderas ni permite atribuir las ausencias a nubes.

## #66 ACEPTADO

MY 202603 es la referencia principal para mantener la versión de IFOP 2024–2025, con corte explícito. NRT se conserva como sensibilidad acotada. De los diez días en solapamiento efectivo (20–29 de octubre), ocho tuvieron valor finito en ambos productos. En esos ocho días, la mediana de log10(NRT) − log10(MY) fue 0 y el máximo absoluto fue 0,05695. Esto no acredita equivalencia fuera de la ventana. Los productos usan insumos distintos y el retraso típico de MY documentado por el productor no garantiza una fecha de disponibilidad. [Brando et al. 2024, §2](https://www.mdpi.com/2072-4292/16/23/4588).

## Reproducción privada de los recuentos

```python
import json
from collections import Counter
from io import BytesIO
from zipfile import ZipFile
import numpy as np
from openpyxl import load_workbook

my, nrt = json.load(open("/tmp/pm46/result.json"))
with ZipFile("upload/Informacion_SAIP.zip") as archive:
    book = load_workbook(BytesIO(archive.read("Informacion SAIP.xlsx")),
                         read_only=True, data_only=True)
days = Counter(r[7].date().isoformat()
               for r in book["Desembarque"].iter_rows(min_row=7, values_only=True)
               if r[3] == "Portales" and r[9] == "Merluza Comun"
               and r[11] in {"Enmalle", "Espinel"})
for product in (my, nrt):
    chl = product["chl"]
    counts = Counter()
    weighted = Counter()
    for day, rows in days.items():
        status = "outside_axis" if day not in chl else (
            "missing" if chl[day] is None else "finite")
        counts[status] += 1
        weighted[status] += rows
    print(product["version"], product["valid_axis_first"], product["valid_axis_last"],
          len(chl), sum(v is not None for v in chl.values()), dict(counts), dict(weighted),
          sum(r["bytes"] for r in product["manifest"]))
a, b = my["chl"], nrt["chl"]
overlap = sorted(a.keys() & b.keys())
matched = [d for d in overlap if a[d] is not None and b[d] is not None]
delta = [np.log10(b[d]) - np.log10(a[d]) for d in matched if a[d] > 0 and b[d] > 0]
print("overlap", overlap, "paired", len(matched), "log10", len(delta),
      np.median(delta) if delta else None, max(map(abs, delta),default=None))
```

El censo habilita preparar un cruce descriptivo por recalada en MY 2026. Sigue pendiente cuantificar soporte por mes y arte, y la sensibilidad de kilos a la fila atípica. No acredita cruce por faena.
