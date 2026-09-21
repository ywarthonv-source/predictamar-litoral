"""
Automatizacion diaria del ranking — PredictaMAR Litoral
=====================================================================

QUE HACE:
Corre el motor de puntaje, averigua sola cual es la fecha mas reciente que
TODOS los productos cubren, y deja el resultado escrito para que la aplicacion
lo lea al instante. La app no consulta Copernicus: lee un archivo.

HORARIOS (hora de Peru, decision del proyecto):
  02:00  cubre la salida de madrugada (5 a 7 de la manana)
  14:00  cubre la salida de tarde (4 a 7)

POR QUE LAS DOS CORRIDAS NO TRAEN LO MISMO:
Copernicus publica alrededor de las 07:00 hora de Peru, y lo que publica es el
mar del dia anterior. Entonces:
  - la corrida de las 14:00 es la FRESCA: toma lo publicado esa manana;
  - la de las 02:00 llega antes de la publicacion del dia, asi que normalmente
    encuentra lo mismo que ya tenia la de las 14:00 del dia anterior.
La de madrugada NO es redundante: actua como respaldo si la de las 14:00 fallo
por conexion o por un retraso de Copernicus, y deja el archivo listo por si el
pescador abre la aplicacion a las 5 de la manana.

REGLA CENTRAL — NUNCA DEJAR LA PANTALLA EN BLANCO:
Si una corrida falla, el ultimo resultado valido SE CONSERVA y se sirve con su
antiguedad declarada. Un pescador prefiere ver "datos de hace 2 dias" a ver una
pantalla vacia. Lo que no se hace jamas es presentar dato viejo como si fuera
de hoy: la antiguedad viaja siempre con el resultado.

SALIDA:
  <salida>/ranking_actual.json      lo que lee la aplicacion
  <salida>/historico/<fecha>.json   una copia por fecha de datos
  <salida>/estado.json              ultima corrida, exito o fallo, antiguedad
  <salida>/corridas.log             bitacora append-only
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
import sys
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

TZ_PERU = ZoneInfo("America/Lima")

# Por encima de esto, el resultado servido deja de considerarse utilizable y la
# aplicacion debe decirlo de forma visible, no en letra chica.
ANTIGUEDAD_MAXIMA_DIAS = 4


def _ahora_peru() -> _dt.datetime:
    return _dt.datetime.now(TZ_PERU)


def _log(destino: Path, texto: str) -> None:
    linea = f"{_ahora_peru().isoformat(timespec='seconds')}  {texto}"
    print(linea.encode("ascii", "replace").decode("ascii"), flush=True)
    with (destino / "corridas.log").open("a", encoding="utf-8") as fh:
        fh.write(linea + "\n")


def fecha_mas_reciente_comun(zona) -> _dt.date | None:
    """Pregunta a Copernicus hasta que dia llega cada producto y devuelve el
    tope comun. No se asume el retraso: se mide en cada corrida, porque varia."""
    import scoring_engine as S

    tope = None
    for v in S.PESOS:
        mejor = None
        for _cid, ini, fin in S.ventana_disponible(v, zona.lat, zona.lon):
            if ini is not None and (mejor is None or fin > mejor):
                mejor = fin
        if mejor is None:
            return None
        tope = mejor if tope is None else min(tope, mejor)
    return tope


def correr(salida: Path, zona_key: str, n: int) -> int:
    import scoring_engine as S

    salida.mkdir(parents=True, exist_ok=True)
    (salida / "historico").mkdir(exist_ok=True)
    zona = S.ZONAS[zona_key]

    actual = salida / "ranking_actual.json"
    estado = salida / "estado.json"
    hoy = _ahora_peru().date()

    _log(salida, f"INICIO corrida  zona={zona_key}")

    try:
        fecha = fecha_mas_reciente_comun(zona)
        if fecha is None:
            raise RuntimeError("Ningun producto respondio al consultar cobertura.")
        _log(salida, f"fecha mas reciente comun a todos los productos: {fecha}")

        # Si ya se calculo esa fecha, no se vuelve a descargar.
        previo = None
        if actual.is_file():
            try:
                previo = json.loads(actual.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                previo = None
        if previo and previo.get("fecha_datos") == fecha.isoformat():
            _log(salida, "la fecha vigente ya estaba calculada; no se redescarga")
            _escribir_estado(estado, "SIN_CAMBIOS", fecha, hoy, None)
            return 0

        r = S.ejecutar(zona, fecha, n_entregar=n)
        if not r["puntos"]:
            raise RuntimeError("El motor no devolvio ningun punto evaluable.")

        r["generado_peru"] = _ahora_peru().isoformat(timespec="seconds")
        r["antiguedad_dias"] = (hoy - fecha).days

        texto = json.dumps(r, ensure_ascii=False, indent=1)
        (salida / "historico" / f"{fecha.isoformat()}.json").write_text(texto, encoding="utf-8")

        # Escritura atomica: si el proceso muere a medias, la aplicacion nunca
        # encuentra un archivo truncado.
        tmp = actual.with_suffix(".json.tmp")
        tmp.write_text(texto, encoding="utf-8")
        tmp.replace(actual)

        _log(salida, f"OK  {len(r['puntos'])} puntos  datos del {fecha}  "
                     f"antiguedad {r['antiguedad_dias']}d  "
                     f"orden_significativo={r['orden_significativo']}")
        _escribir_estado(estado, "OK", fecha, hoy, None)
        return 0

    except Exception as exc:  # noqa: BLE001
        _log(salida, f"FALLO  {type(exc).__name__}: {exc}")
        (salida / "ultimo_error.txt").write_text(
            f"{_ahora_peru().isoformat()}\n\n{traceback.format_exc()}", encoding="utf-8")

        # El resultado anterior NO se toca. Se sirve con su antiguedad declarada.
        if actual.is_file():
            try:
                prev = json.loads(actual.read_text(encoding="utf-8"))
                fprev = _dt.date.fromisoformat(prev["fecha_datos"])
                ant = (hoy - fprev).days
                prev["antiguedad_dias"] = ant
                prev["dato_desactualizado"] = ant > ANTIGUEDAD_MAXIMA_DIAS
                actual.write_text(json.dumps(prev, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
                _log(salida, f"se conserva el resultado del {fprev} (antiguedad {ant}d)"
                             + ("  MARCADO COMO DESACTUALIZADO" if ant > ANTIGUEDAD_MAXIMA_DIAS else ""))
                _escribir_estado(estado, "FALLO_CON_RESPALDO", fprev, hoy, str(exc)[:200])
            except Exception:  # noqa: BLE001
                _escribir_estado(estado, "FALLO_SIN_RESPALDO", None, hoy, str(exc)[:200])
        else:
            _log(salida, "no hay resultado previo: la aplicacion no tiene que mostrar")
            _escribir_estado(estado, "FALLO_SIN_RESPALDO", None, hoy, str(exc)[:200])
        return 1


def _escribir_estado(p: Path, estado: str, fecha, hoy, error) -> None:
    p.write_text(json.dumps({
        "estado": estado,
        "ultima_corrida_peru": _ahora_peru().isoformat(timespec="seconds"),
        "fecha_datos_servida": fecha.isoformat() if fecha else None,
        "antiguedad_dias": (hoy - fecha).days if fecha else None,
        "antiguedad_maxima_aceptable": ANTIGUEDAD_MAXIMA_DIAS,
        "error": error,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------------
# INSTALACION DE LAS TAREAS PROGRAMADAS (Windows)
# ---------------------------------------------------------------------------


def instrucciones(salida: Path) -> int:
    py = sys.executable
    script = Path(__file__).resolve()
    print(f"""
======================================================================
PROGRAMAR LAS DOS CORRIDAS DIARIAS (Windows)
======================================================================

Abrir PowerShell COMO ADMINISTRADOR y pegar estas dos lineas:

schtasks /create /tn "PredictaMAR 02" /tr "\\"{py}\\" \\"{script}\\" --salida \\"{salida}\\"" /sc daily /st 02:00 /f

schtasks /create /tn "PredictaMAR 14" /tr "\\"{py}\\" \\"{script}\\" --salida \\"{salida}\\"" /sc daily /st 14:00 /f

Comprobar que quedaron:      schtasks /query /tn "PredictaMAR 02"
Forzar una corrida de prueba: schtasks /run   /tn "PredictaMAR 14"
Borrarlas:                    schtasks /delete /tn "PredictaMAR 02" /f

ADVERTENCIA: la tarea solo corre si el equipo esta encendido a esa hora.
Para operacion real conviene un servidor, no una laptop.
======================================================================
""")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Corrida diaria del ranking")
    ap.add_argument("--salida", type=Path, default=Path("publicado"))
    ap.add_argument("--zona", default="pucusana")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--instalar", action="store_true",
                    help="Muestra los comandos para programar las dos corridas.")
    a = ap.parse_args(argv)

    if a.instalar:
        return instrucciones(a.salida.resolve())
    return correr(a.salida, a.zona, a.n)


if __name__ == "__main__":
    raise SystemExit(main())
