"""
Motor de puntaje — PredictaMAR Litoral
=====================================================================

QUE HACE:
Genera puntos candidatos en la zona de faena, consulta Copernicus para cada
uno, calcula un indice de compatibilidad ambiental y devuelve los mejores
ordenados, en el formato JSON que la cascara ya sabe leer.

QUE ENTREGA Y QUE NO:
Entrega "los lugares donde hoy se dan las mejores condiciones". NO entrega
probabilidad de captura, NO predice presencia de cardumen, y NO distingue
especie: el anexo NASC con el que se calibro no trae asignacion taxonomica,
de modo que lo modelado es biomasa pelagica, que incluye munida.

DE DONDE SALEN LOS PESOS Y LAS CURVAS:
De medicion, no de criterio. Emparejamiento de 10.759 intervalos NASC del
crucero 2602-04 de IMARPE con Copernicus, restringido a la banda 9S-15S
(stock centro, el de Pucusana). Ver pesos_medidos_biomasa_v1.yaml.
AUC dejando regiones fuera: 0.616. Dejando fechas fuera: 0.637.
El 0.852 de la particion aleatoria NO se reporta: mide memoria espacial.

POR QUE LA BANDA CENTRO Y NO TODO EL LITORAL:
Al separar por stock, la salinidad INVIERTE su direccion (de +0.10 a -0.90)
y la relacion resultante coincide con Castillo 2022: la zona optima de la
anchoveta se define por las Aguas Costeras Frias, que son el extremo de baja
salinidad. La relacion del litoral completo estaba confundida por mezclar el
dominio ecuatorial con el subtropical. Lujan (2016) analiza por stock por
esta misma razon.

DEGRADACION EN VEZ DE NULO:
Si falta una variable, el puntaje se calcula con las disponibles y se DECLARA
cuales faltaron. No se imputa, no se rellena con cero, no se redistribuye
peso a capas estaticas. Pero tampoco se devuelve nulo: devolver nulo por una
variable ausente fue lo que dejo la pantalla en blanco.
Por debajo de COBERTURA_MINIMA el punto se descarta explicitamente.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# CALIBRACION
# ---------------------------------------------------------------------------

CALIBRACION_ID = "banda_centro_2602-04_v1"
ETIQUETA = "BIOMASA_PELAGICA_TOTAL"

AUC_REGIONES_FUERA = 0.616
AUC_FECHAS_FUERA = 0.637

# Fraccion minima del peso total que debe estar disponible para emitir puntaje.
COBERTURA_MINIMA = 0.60

# Variable que ademas actua como FILTRO DE TIERRA. El producto de clorofila es
# gap-free (rellena nubes), asi que una celda sin dato a 4 km de resolucion
# indica tierra o franja costera, no nubosidad. Si falta, el punto no se
# entrega: en la primera corrida real los puntos sin clorofila resultaron ser
# todos costeros, y ganaban el ranking por el frio del afloramiento usando solo
# tres variables contra cinco.
VARIABLE_FILTRO_TIERRA = "clorofila"

# VENTANA TEMPORAL POR VARIABLE — decidida por medicion, no por criterio.
#
# Se comparo, sobre los 10.759 intervalos NASC de IMARPE en la banda de
# Pucusana, cuanto varia cada variable ENTRE PUNTOS de un mismo dia contra
# cuanto se mueve DE UN DIA AL SIGUIENTE:
#
#   variable         entre puntos   entre dias   manda
#   clorofila            1.63          3.68      EL DIA
#   sst_ostia            1.04          0.22      el punto
#   salinidad           0.066         0.025      el punto
#   nivel_mar           0.012         0.004      el punto
#   prod_primaria        24.0           5.4      el punto
#
# Cuatro de cinco cambian mas de un punto a otro que de un dia a otro: para
# ellas el dia mas reciente basta y una ventana no aporta nada medible.
#
# La clorofila es la excepcion y es ademas la variable de mayor peso segun
# Lujan (2016) y segun los datos propios. Se mueve mas del doble entre dias
# que entre puntos, de modo que un solo dia puede ser un valor atipico. Se
# promedian 5 dias: suficiente para que un dato raro no mande, corto para no
# borrar un florecimiento real. Treinta dias describiria el mes, no el dia.
#
# Efecto lateral util: al promediar, el retraso de publicacion de 1-2 dias
# deja de importar para esta variable.
VENTANA_DIAS = {
    "clorofila": 5,
    "sst_ostia": 1,
    "salinidad": 1,
    "nivel_mar": 1,
    "prod_primaria": 1,
}

PESOS = {
    "sst_ostia": 24.2,
    "nivel_mar": 22.6,
    "salinidad": 21.0,
    "clorofila": 19.0,
    "prod_primaria": 13.2,
}

# Curvas crudo -> favorabilidad 0-1, por regresion isotonica sobre los datos
# de la banda centro. La DIRECCION esta medida y ademas respaldada por
# literatura; la forma interior es el ajuste monotono, no una suposicion.
CURVAS = {
    "clorofila": [(0.82, 0.00), (2.63, 0.30), (4.41, 0.35), (6.44, 0.38), (8.73, 0.46), (14.87, 1.00)],
    "sst_ostia": [(17.06, 1.00), (19.50, 0.91), (20.34, 0.54), (21.10, 0.38), (22.15, 0.25), (23.32, 0.10), (24.30, 0.00)],
    "nivel_mar": [(0.11, 0.00), (0.1215, 0.25), (0.1245, 0.37), (0.15, 0.50), (0.16, 1.00), (0.18, 1.00)],
    "prod_primaria": [(35.33, 0.00), (41.52, 0.28), (45.49, 0.44), (50.41, 0.62), (117.61, 0.90), (158.50, 1.00), (207.44, 1.00)],
    "salinidad": [(34.67, 1.00), (34.78, 0.92), (34.85, 0.76), (34.90, 0.60), (34.95, 0.34), (35.05, 0.00), (35.10, 0.00)],
}

# Variables que se descargan pero NO entran al puntaje. Solo sirven para
# calcular hacia donde se desplaza el agua entre el dato y la hora de pesca.
SOLO_DERIVA = ("corriente_u", "corriente_v")

DATASETS = {
    "corriente_u": dict(
        ids=("cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m",),
        var="uo", max_km=12.0, depth=1.0, unidad="m_s"),
    "corriente_v": dict(
        ids=("cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m",),
        var="vo", max_km=12.0, depth=1.0, unidad="m_s"),
    "clorofila": dict(
        # El identificador "myint" que probamos NO existe: Copernicus respondio
        # "please check that the dataset exists". Queda un hueco entre el fin
        # del producto reprocesado y la ventana movil del de tiempo real.
        ids=("cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D",
             "cmems_obs-oc_glo_bgc-plankton_my_l4-gapfree-multi-4km_P1D"),
        var="CHL", max_km=6.5, depth=None, unidad="mg_m3"),
    "sst_ostia": dict(
        ids=("METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2",),
        var="analysed_sst", max_km=10.0, depth=None, unidad="kelvin"),
    "salinidad": dict(
        ids=("cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m",),
        var="so", max_km=12.0, depth=1.0, unidad="psu"),
    "nivel_mar": dict(
        ids=("cmems_mod_glo_phy_anfc_0.083deg_P1D-m",),
        var="zos", max_km=12.0, depth=None, unidad="m"),
    "prod_primaria": dict(
        ids=("cmems_mod_glo_bgc-bio_anfc_0.25deg_P1D-m",),
        var="nppv", max_km=30.0, depth=1.0, unidad="mg_c_m3_dia"),
}

# Advertencias que viajan SIEMPRE con la salida.
ADVERTENCIAS = [
    "Indice experimental de compatibilidad ambiental. No es probabilidad de captura.",
    "No distingue especie: el anexo NASC de calibracion no trae asignacion taxonomica. "
    "La biomasa detectada incluye munida, que comparte distribucion costera con la anchoveta "
    "y no es objetivo de pesca.",
    f"Capacidad predictiva medida (AUC fuera de region): {AUC_REGIONES_FUERA}. "
    "Es señal real por encima del azar, pero modesta.",
    "La productividad primaria proviene del producto BGC a 0.25 grados. Ese mismo producto "
    "fallo la verificacion contra observacion para la oxiclina (correlacion 0.098). "
    "Pendiente de verificar.",
]

# ---------------------------------------------------------------------------
# ZONA
# ---------------------------------------------------------------------------

def _p(texto: str = "") -> None:
    """Imprime sin depender de la codificacion de la consola."""
    print(texto.encode("ascii", "replace").decode("ascii"), flush=True)


PUCUSANA_LAT = -12.4772
PUCUSANA_LON = -76.7953


@dataclass(frozen=True)
class Zona:
    nombre: str
    lat: float
    lon: float
    dist_min_km: float
    dist_max_km: float
    # Rumbos SEAWARD unicamente. El semicirculo 180-360 parecia razonable pero
    # incluye el norte y el sur, que en esta costa corren PARALELOS a la orilla:
    # 20 km al norte de Pucusana no es mar adentro, es Punta Hermosa. En la
    # primera corrida real los cinco ganadores salieron con rumbo 336-360 y se
    # quedaron sin clorofila por estar sobre la franja costera.
    rumbo_min: float = 200.0
    rumbo_max: float = 310.0


ZONAS = {
    "pucusana": Zona("Pucusana", PUCUSANA_LAT, PUCUSANA_LON, 8.0, 80.0),
}


# ---------------------------------------------------------------------------
# GEOMETRIA
# ---------------------------------------------------------------------------


def destino(lat: float, lon: float, rumbo_deg: float, dist_km: float):
    R = 6371.0088
    b = math.radians(rumbo_deg)
    d = dist_km / R
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1),
                         math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 2 * R * math.asin(min(1.0, math.sqrt(a)))


def generar_malla(z: Zona, paso_km: float = 4.0, paso_rumbo: float = 12.0):
    """Puntos candidatos en abanico sobre el mar, entre las distancias declaradas."""
    pts = []
    d = z.dist_min_km
    while d <= z.dist_max_km:
        r = z.rumbo_min
        while r <= z.rumbo_max:
            la, lo = destino(z.lat, z.lon, r, d)
            pts.append(dict(lat=round(la, 5), lon=round(lo, 5),
                            dist_km=round(d, 1), rumbo=round(r, 0)))
            r += paso_rumbo
        d += paso_km
    return pts


# ---------------------------------------------------------------------------
# PUNTAJE
# ---------------------------------------------------------------------------


def favorabilidad(variable: str, valor: float) -> float:
    """Interpola la curva medida. Fuera de rango se mantiene el extremo:
    la curva no dice nada mas alla de donde se midio, y extrapolar seria
    inventar."""
    c = CURVAS[variable]
    if valor <= c[0][0]:
        return c[0][1]
    if valor >= c[-1][0]:
        return c[-1][1]
    for (x0, y0), (x1, y1) in zip(c, c[1:]):
        if x0 <= valor <= x1:
            if x1 == x0:
                return y1
            return y0 + (valor - x0) * (y1 - y0) / (x1 - x0)
    return c[-1][1]


def puntuar(valores: dict) -> dict:
    """Combina lo disponible y declara lo que falto. NUNCA imputa."""
    aporte, usado, faltantes = {}, 0.0, []
    for v, peso in PESOS.items():
        x = valores.get(v)
        if x is None:
            faltantes.append(v)
            continue
        f = favorabilidad(v, x)
        aporte[v] = dict(valor=round(x, 4), favorabilidad=round(f, 3),
                         peso=peso, aporta=round(f * peso, 2))
        usado += peso

    total = sum(PESOS.values())
    cobertura = usado / total

    if VARIABLE_FILTRO_TIERRA in faltantes:
        return dict(puntaje=None, estado="PROBABLE_TIERRA_O_COSTA",
                    cobertura_pct=round(100 * cobertura, 1), faltantes=faltantes,
                    detalle=aporte)

    if cobertura < COBERTURA_MINIMA:
        return dict(puntaje=None, estado="COBERTURA_INSUFICIENTE",
                    cobertura_pct=round(100 * cobertura, 1), faltantes=faltantes,
                    detalle=aporte)

    puntaje = sum(a["aporta"] for a in aporte.values()) / usado
    return dict(puntaje=round(100 * puntaje, 1),
                estado="COMPLETO" if not faltantes else "PARCIAL",
                cobertura_pct=round(100 * cobertura, 1),
                faltantes=faltantes, detalle=aporte)


# ---------------------------------------------------------------------------
# CONSULTA
# ---------------------------------------------------------------------------


def _extraer(variable: str, fecha: _dt.date, pts: list) -> dict:
    """Un recorte por variable para toda la zona; extraccion local en memoria."""
    import numpy as np
    import copernicusmarine

    cfg = DATASETS[variable]
    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    m = 0.4
    dias = VENTANA_DIAS.get(variable, 1)
    # La ventana es RETROSPECTIVA: termina en la fecha pedida y se extiende
    # hacia atras. Nunca incluye dias posteriores.
    ini = _dt.datetime.combine(fecha - _dt.timedelta(days=dias - 1), _dt.time(0, 0),
                               tzinfo=_dt.timezone.utc)
    fin = _dt.datetime.combine(fecha, _dt.time(23, 59, 59), tzinfo=_dt.timezone.utc)

    ds = None
    for cid in cfg["ids"]:
        try:
            kw = {}
            if cfg["depth"] is not None:
                kw["minimum_depth"] = 0.0
                kw["maximum_depth"] = cfg["depth"]
            ds = copernicusmarine.open_dataset(
                dataset_id=cid, variables=[cfg["var"]],
                minimum_latitude=min(lats) - m, maximum_latitude=max(lats) + m,
                minimum_longitude=min(lons) - m, maximum_longitude=max(lons) + m,
                start_datetime=ini, end_datetime=fin, **kw)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"      {cid}: {str(exc)[:140]}", file=sys.stderr, flush=True)
            ds = None
    if ds is None:
        print(f"      -> {variable}: ningun dataset respondio", file=sys.stderr, flush=True)
        return {}

    da = ds[cfg["var"]]
    n_dias_usados = int(da.sizes["time"]) if "time" in da.dims else 1
    if "time" in da.dims:
        if da.sizes["time"] == 0:
            print(f"      -> {variable}: el recorte no tiene ningun paso de tiempo "
                  f"para {fecha}. La fecha esta fuera de la cobertura del producto.",
                  file=sys.stderr, flush=True)
            return {}
        # Promedio temporal POR CELDA, antes de elegir celda. Al reves
        # saltaria de celda entre dias y la serie no seria del mismo lugar.
        da = da.mean(dim="time", skipna=True) if dias > 1 else da.isel(time=0)
    if "depth" in da.dims:
        da = da.isel(depth=0)
    da = da.load()

    gl = np.asarray(da["latitude"].values, float)
    go = np.asarray(da["longitude"].values, float)
    gv = np.asarray(da.values, float)

    finitos = int(np.isfinite(gv).sum())
    vent = f"  ventana {dias}d ({n_dias_usados} dias con dato)" if dias > 1 else ""
    print(f"      malla {gv.shape}  lat {gl.min():.3f}..{gl.max():.3f}  "
          f"lon {go.min():.3f}..{go.max():.3f}  celdas con dato: {finitos}/{gv.size}{vent}",
          file=sys.stderr, flush=True)
    if finitos == 0:
        print(f"      -> {variable}: el recorte llego COMPLETO DE NaN.",
              file=sys.stderr, flush=True)
        return {}

    out = {}
    dg = (cfg["max_km"] / 111.0) * 1.5
    for k, p in enumerate(pts):
        mi = np.nonzero(np.abs(gl - p["lat"]) <= dg)[0]
        mj = np.nonzero(np.abs(go - p["lon"]) <= dg / max(math.cos(math.radians(p["lat"])), 0.2))[0]
        if mi.size == 0 or mj.size == 0:
            continue
        sub = gv[np.ix_(mi, mj)]
        la = np.radians(gl[mi])[:, None]
        lo = np.radians(go[mj])[None, :]
        pr, lr = math.radians(p["lat"]), math.radians(p["lon"])
        aa = np.sin((la - pr) / 2) ** 2 + math.cos(pr) * np.cos(la) * np.sin((lo - lr) / 2) ** 2
        d = 2 * 6371.0088 * np.arcsin(np.clip(np.sqrt(aa), 0, 1))
        ok = np.isfinite(sub) & (d <= cfg["max_km"])
        if not ok.any():
            continue
        dd = np.where(ok, d, np.inf)
        ij = np.unravel_index(np.argmin(dd), dd.shape)
        val = float(sub[ij])
        if cfg["unidad"] == "kelvin":
            val -= 273.15
        out[k] = val
    print(f"      -> {variable}: {len(out)}/{len(pts)} puntos resueltos",
          file=sys.stderr, flush=True)
    return out


# ---------------------------------------------------------------------------
# EJECUCION
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# COBERTURA TEMPORAL
# ---------------------------------------------------------------------------


def ventana_disponible(variable: str, lat: float, lon: float):
    """Pregunta a Copernicus QUE FECHAS tiene realmente cada producto.

    Hasta ahora la fecha se elegia a ciegas y se descubria el hueco al fallar.
    Los productos reprocesados terminan hace meses y los de tiempo real guardan
    una ventana movil de semanas; entre ambos puede quedar un vacio. Medirlo es
    mas barato que suponerlo.
    """
    import copernicusmarine

    cfg = DATASETS[variable]
    for cid in cfg["ids"]:
        try:
            kw = {}
            if cfg["depth"] is not None:
                kw["minimum_depth"] = 0.0
                kw["maximum_depth"] = cfg["depth"]
            ds = copernicusmarine.open_dataset(
                dataset_id=cid, variables=[cfg["var"]],
                minimum_latitude=lat - 0.2, maximum_latitude=lat + 0.2,
                minimum_longitude=lon - 0.2, maximum_longitude=lon + 0.2, **kw)
            t = ds["time"].values
            if len(t) == 0:
                continue
            ini = _dt.datetime.utcfromtimestamp(t.min().astype("int64") / 1e9).date()
            fin = _dt.datetime.utcfromtimestamp(t.max().astype("int64") / 1e9).date()
            yield cid, ini, fin
        except Exception as exc:  # noqa: BLE001
            yield cid, None, str(exc)[:90]


def informar_cobertura(zona: Zona) -> int:
    """Lista la ventana real de cada producto y propone la fecha mas reciente
    que TODOS cubren."""
    _p("=" * 74)
    _p("COBERTURA TEMPORAL REAL DE CADA PRODUCTO")
    _p("=" * 74)
    tope_comun = None
    for v in PESOS:
        _p(f"{v}  (peso {PESOS[v]})")
        mejor_fin = None
        for cid, ini, fin in ventana_disponible(v, zona.lat, zona.lon):
            if ini is None:
                _p(f"   FALLA  {cid}")
                _p(f"          {fin}")
            else:
                _p(f"   OK     {cid}")
                _p(f"          {ini}  a  {fin}")
                if mejor_fin is None or fin > mejor_fin:
                    mejor_fin = fin
        if mejor_fin is not None:
            tope_comun = mejor_fin if tope_comun is None else min(tope_comun, mejor_fin)
        _p("")
    _p("=" * 74)
    if tope_comun:
        _p(f"FECHA MAS RECIENTE QUE TODOS LOS PRODUCTOS CUBREN: {tope_comun}")
        _p("")
        _p(f"   python scoring/scoring_engine.py --fecha {tope_comun}")
    else:
        _p("Ningun producto respondio. Revise credenciales y conexion.")
    _p("=" * 74)
    return 0


def ejecutar(zona: Zona, fecha: _dt.date, n_entregar: int = 5,
             paso_km: float = 4.0, paso_rumbo: float = 12.0) -> dict:
    pts = generar_malla(zona, paso_km, paso_rumbo)
    print(f"Malla: {len(pts)} puntos candidatos entre "
          f"{zona.dist_min_km:.0f} y {zona.dist_max_km:.0f} km", file=sys.stderr)

    lecturas = {}
    for v in list(PESOS) + list(SOLO_DERIVA):
        print(f"  consultando {v} ...", file=sys.stderr, flush=True)
        lecturas[v] = _extraer(v, fecha, pts)

    print(file=sys.stderr)
    print("  COBERTURA POR VARIABLE:", file=sys.stderr)
    for v in PESOS:
        n = len(lecturas.get(v, {}))
        print(f"    {v:16} {n:4}/{len(pts)}  (peso {PESOS[v]})", file=sys.stderr)
    disp = sum(PESOS[v] for v in PESOS if lecturas.get(v))
    print(f"    peso disponible en total: {disp:.1f} de {sum(PESOS.values()):.1f} "
          f"(minimo exigido {100*COBERTURA_MINIMA:.0f})", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    evaluados = []
    descartes: dict[str, int] = {}
    for k, p in enumerate(pts):
        vals = {v: lecturas[v].get(k) for v in PESOS}
        vals = {a: b for a, b in vals.items() if b is not None}
        r = puntuar(vals)
        if r["puntaje"] is None:
            descartes[r["estado"]] = descartes.get(r["estado"], 0) + 1
            continue
        # La corriente viaja con el punto: la aplicacion calcula con ella
        # donde estara esa masa de agua a la hora del primer lance, sin
        # volver a descargar nada.
        cu = lecturas.get("corriente_u", {}).get(k)
        cv = lecturas.get("corriente_v", {}).get(k)
        evaluados.append({**p, **r, "corriente_u": cu, "corriente_v": cv})

    # Un punto medido con menos variables NO puede desplazar a uno medido con
    # todas. Primero se ordena por cobertura, despues por puntaje: de lo
    # contrario el motor premia aquello de lo que menos sabe.
    evaluados.sort(key=lambda x: (-x["cobertura_pct"], -x["puntaje"]))

    # DISTRIBUCION COMPLETA — la prueba que decide si el ranking dice algo.
    # Que los cinco mejores se parezcan entre si es normal: significa que hay
    # cinco buenos sitios. Lo que importa es si el MEJOR se separa del PEOR de
    # todos los candidatos. Si no se separa, el mar esta parejo ese dia y
    # señalar un punto es ruido, por mucho que las coordenadas sean distintas.
    import statistics as _st
    _ps = sorted((e["puntaje"] for e in evaluados), reverse=True)
    reparto = None
    if len(_ps) >= 10:
        reparto = {
            "n": len(_ps),
            "mejor": _ps[0],
            "p90": round(_ps[int(len(_ps) * 0.10)], 1),
            "mediana": round(_st.median(_ps), 1),
            "p10": round(_ps[int(len(_ps) * 0.90)], 1),
            "peor": _ps[-1],
            "rango": round(_ps[0] - _ps[-1], 1),
            "desviacion": round(_st.pstdev(_ps), 1),
        }
        # Criterio: si el mejor no supera al peor por mas de 10 puntos sobre
        # 100, la zona esta plana y el ranking no distingue nada util.
        reparto["mar_diferenciado"] = reparto["rango"] >= 10.0
    mejores = evaluados[:n_entregar]

    # PERCENTIL DE CADA CANDIDATO dentro del mar de ese dia. Es lo que permite
    # decirle al pescador "esta zona esta entre el 10% mejor del mar de hoy"
    # sin hablar de probabilidad de captura: compara zonas contra zonas, no
    # promete pescado.
    _orden = sorted((e["puntaje"] for e in evaluados))
    _n = len(_orden)
    import bisect as _bs
    for e in evaluados:
        # fraccion de candidatos que esta zona supera
        e["percentil"] = round(_bs.bisect_left(_orden, e["puntaje"]) / max(_n - 1, 1), 3)

    # Si los mejores estan empatados dentro del ruido, no se presentan como
    # primero y segundo: el orden no significaria nada.
    empate = (len(mejores) > 1 and (mejores[0]["puntaje"] - mejores[-1]["puntaje"]) < 5.0)

    return {
        "schema_version": "ranking_v1",
        "generado": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "fecha_datos": fecha.isoformat(),
        "zona": zona.nombre,
        "etiqueta_taxonomica": ETIQUETA,
        "calibracion_id": CALIBRACION_ID,
        "titulo": "Zonas con mejores condiciones ambientales",
        "orden_significativo": not empate,
        "nota_empate": ("Los puntos entregados estan dentro del margen de ruido entre si: "
                        "tratelos como equivalentes, no como un ranking.") if empate else None,
        "reparto_puntajes": reparto,
        # TODOS los candidatos, no solo los 5 mejores del mar entero. Si el
        # pescador pide "hasta 10 km" desde su punto, la aplicacion tiene que
        # poder encontrar las MEJORES dentro de su radio. Con solo 5 guardados
        # solo podia mostrarle cuales de esos 5 caian cerca, que no es lo mismo.
        "candidatos": [
            {
                "lat": e["lat"], "lon": e["lon"],
                "puntaje": e["puntaje"],
                "percentil": e["percentil"],
                "estado": e["estado"],
                "corriente_u": e.get("corriente_u"),
                "corriente_v": e.get("corriente_v"),
                "detalle": {k: {"valor": v["valor"], "favorabilidad": v["favorabilidad"]}
                            for k, v in e["detalle"].items()},
            } for e in evaluados
        ],
        # TODOS los candidatos, no solo los mejores. La aplicacion filtra desde
        # el punto de partida que elija el pescador y la distancia que este
        # dispuesto a navegar, sin volver a consultar Copernicus.
        "malla": [
            {"lat": e["lat"], "lon": e["lon"],
             "dist_caleta_km": e["dist_km"], "puntaje": e["puntaje"],
             "cobertura_pct": e["cobertura_pct"]}
            for e in evaluados
        ],
        "candidatos_evaluados": len(evaluados),
        "candidatos_generados": len(pts),
        "descartados": descartes,
        "puntos": [
            {
                "orden": i + 1,
                "lat": p["lat"], "lon": p["lon"],
                "distancia_km": p["dist_km"],
                "puntaje": p["puntaje"],
                "estado": p["estado"],
                "cobertura_pct": p["cobertura_pct"],
                "faltantes": p["faltantes"],
                "corriente_u": p.get("corriente_u"),
                "corriente_v": p.get("corriente_v"),
                "detalle": p["detalle"],
            } for i, p in enumerate(mejores)
        ],
        "ventana_por_variable": {v: VENTANA_DIAS.get(v, 1) for v in PESOS},
        "nota_ventana": (
            "La clorofila se promedia sobre 5 dias retrospectivos porque su "
            "variacion entre dias supera a la variacion entre puntos (3.68 contra "
            "1.63 medido sobre los intervalos NASC). El resto usa el dia pedido."),
        "deriva": {
            "hora_referencia_utc": 12,
            "tope_horas_confiable": 12,
            "explicacion": (
                "corriente_u y corriente_v vienen en m/s en cada punto. El agua "
                "recorre velocidad por tiempo: en la franja de Pucusana la mediana "
                "es 0,215 m/s, o sea unos 4,6 km en 6 horas, comparable al tamano "
                "de una celda de clorofila (4 km). La masa de agua senalada se "
                "desplaza, asi que la coordenada calculada deja de corresponder a "
                "ese parche a medida que pasan las horas."),
            "limitacion": (
                "La corriente es media diaria de un modelo a 9 km: no incluye marea "
                "ni deriva por viento. Mas alla de unas 12 horas la proyeccion "
                "acumula error y deja de ser confiable. Ademas parte de la senal "
                "(el afloramiento) esta anclada al fondo y NO se desplaza con el "
                "agua, de modo que la correccion es una aproximacion, no una "
                "posicion exacta."),
        },
        "advertencias": ADVERTENCIAS,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Motor de puntaje PredictaMAR Litoral")
    ap.add_argument("--zona", default="pucusana", choices=sorted(ZONAS))
    ap.add_argument("--fecha", default=None, help="AAAA-MM-DD; por defecto ayer UTC")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--cobertura", action="store_true",
                    help="Solo informa que fechas tiene cada producto. No calcula nada.")
    ap.add_argument("--salida", type=Path, default=Path("ranking.json"))
    ap.add_argument("--paso-km", type=float, default=4.0)
    ap.add_argument("--paso-rumbo", type=float, default=12.0)
    a = ap.parse_args(argv)

    if a.cobertura:
        return informar_cobertura(ZONAS[a.zona])

    fecha = (_dt.date.fromisoformat(a.fecha) if a.fecha
             else _dt.datetime.now(_dt.timezone.utc).date() - _dt.timedelta(days=1))

    r = ejecutar(ZONAS[a.zona], fecha, a.n, a.paso_km, a.paso_rumbo)
    a.salida.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("=" * 62)
    print(f"{r['titulo']} — {r['zona']} — datos del {r['fecha_datos']}")
    print("=" * 62)
    print(f"Evaluados {r['candidatos_evaluados']} de {r['candidatos_generados']} candidatos")
    for k, v in r.get("descartados", {}).items():
        print(f"  descartados por {k}: {v}")
    print()
    for p in r["puntos"]:
        fal = f"  [faltan: {', '.join(p['faltantes'])}]" if p["faltantes"] else ""
        print(f"  {p['orden']}. {p['lat']:9.5f}, {p['lon']:9.5f}   "
              f"{p['distancia_km']:5.1f} km   puntaje {p['puntaje']:5.1f}"
              f"   ({p['estado']}, {p['cobertura_pct']:.0f}%){fal}")
    d = r.get("reparto_puntajes")
    if d:
        print()
        print("  REPARTO DE PUNTAJES SOBRE LOS {} CANDIDATOS:".format(d["n"]))
        print(f"    mejor   {d['mejor']:5.1f}")
        print(f"    10% sup {d['p90']:5.1f}")
        print(f"    mediana {d['mediana']:5.1f}")
        print(f"    10% inf {d['p10']:5.1f}")
        print(f"    peor    {d['peor']:5.1f}")
        print(f"    rango   {d['rango']:5.1f}   desviacion {d['desviacion']:.1f}")
        print()
        print("    -> " + ("EL MAR ESTA DIFERENCIADO: ir al mejor punto vale la pena."
                           if d["mar_diferenciado"] else
                           "MAR PAREJO: los candidatos se parecen demasiado entre si; "
                           "hoy el ranking no distingue nada util."))

    if not r["orden_significativo"]:
        print()
        print("  AVISO: " + r["nota_empate"])
    print()
    print(f"Escrito: {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
