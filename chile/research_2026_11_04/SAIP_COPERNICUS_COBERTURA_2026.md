# Cobertura nominal de clorofila L3 para SAIP 2026

6 de noviembre de 2026. #65 PARCIAL. Contraste de catálogo y fechas antes de leer el campo en Portales.

Consulté por HTTPS el STAC oficial, filtrando los enlaces item a plankton multisensor L3 4 km P1D. Las versiones que exponen un eje temporal nominal son:

| Versión | Extensión nominal | SHA-256 del item |
|---|---|---|
| [MY 202603](https://stac.marine.copernicus.eu/metadata/OCEANCOLOUR_GLO_BGC_L3_MY_009_103/cmems_obs-oc_glo_bgc-plankton_my_l3-multi-4km_P1D_202603/dataset.stac.json) | 1997-09-04 a 2026-10-29 | `1fa7ba6488685c56690374c285f1bb67b811a937c84653e725bcd5564f02c23a` |
| [NRT 202411](https://stac.marine.copernicus.eu/metadata/OCEANCOLOUR_GLO_BGC_L3_NRT_009_101/cmems_obs-oc_glo_bgc-plankton_nrt_l3-multi-4km_P1D_202411/dataset.stac.json) | 2024-09-30 a 2026-11-05 | `86d951115ed31c6d99946cad91f6c22a2e8fcf75648a22dd6b78ba4e424d2552` |

También aparecían items 202611 para MY y NRT. Los items consultados no exponían dimensión temporal ni assets `geoChunked` o `timeChunked`. No se seleccionaron como reemplazos.

Para reproducir la lectura de metadatos de cada enlace, guardar su JSON y ejecutar `sha256sum item.json; jq '.properties["cube:dimensions"].time, (.assets | keys)' item.json`. El catálogo es mutable. La evidencia de esta ronda es su estado en la fecha indicada.

## Intersección con las fechas privadas

Con el ZIP verificado en [la auditoría SAIP](SERNAPESCA_SAIP_2026.md), filtré Portales, Merluza Comun, enmalle y espinel. Conservé las 2.261 filas para el censo de cobertura, incluida la anomalía de peso, que se trata por separado en cualquier análisis de kilos. Hay 171 días distintos de recalada. Comparé la fecha, sin hora, con los extremos nominales de cada item:

- MY 202603 deja 19 filas en tres días posteriores a su extremo. El resto, 2.242 filas en 168 días, cae dentro de la extensión nominal.
- NRT 202411 incluye nominalmente las 2.261 filas y los 171 días. Esto no verifica el eje ARCO ni observaciones finitas en la celda de referencia.

Consulta reproducible sobre el archivo privado, sin volcar filas:

```python
from io import BytesIO
from zipfile import ZipFile
from openpyxl import load_workbook

with ZipFile("Informacion_SAIP.zip") as archive:
    workbook = load_workbook(BytesIO(archive.read("Informacion SAIP.xlsx")),
                             read_only=True, data_only=True)
sheet = workbook["Desembarque"]
dates = [r[7].date().isoformat() for r in sheet.iter_rows(min_row=7, values_only=True)
         if r[3] == "Portales" and r[9] == "Merluza Comun"
         and r[11] in {"Enmalle", "Espinel"}]
print(len(dates), len(set(dates)))
for end in ("2026-10-29", "2026-11-05"):
    late = [d for d in dates if d > end]
    print(end, len(late), len(set(late)))
```

## Dictamen provisional

Priorizar un censo ARCO de NRT en la misma celda de Portales y contrastar MY en el solapamiento, conservando versión, fecha, unidades y motivo de huecos. Mantener MY 2024–2025 y NRT 2026 separados hasta caracterizar diferencias. No rellenar el extremo MY con NRT sin declarar el cambio de producto. En esta ronda se verificaron metadatos y solapamiento nominal. No se leyeron valores de clorofila ni se certificó la disponibilidad local diaria.
