"""
Suite sintética para validation/inspect_imarpe.py

Enteramente sintética, SIN red y SIN un solo dato real de IMARPE. Los libros de
prueba se construyen aquí con encabezados inventados a propósito -- inventados
para la prueba, nunca para el módulo -- de modo que quede demostrado que el
inspector no depende de conocer los encabezados reales.

Ninguna prueba escribe fuera de tmp_path, ninguna abre el Excel restringido y
ninguna necesita red.

Ejecutar:  python -m pytest tests/test_inspect_imarpe.py -v
"""

import datetime as dt
import inspect as py_inspect
from pathlib import Path

import openpyxl
import pandas as pd
import pytest
import yaml

import validation.inspect_imarpe as vi

ENV = "PREDICTAMAR_IMARPE_XLSX"

# Encabezados FICTICIOS: no son los de la entrega real y no deben serlo.
H_BOT = ["col_fecha_sint", "col_hora_sint", "col_lat_sint", "col_lon_sint",
         "col_estacion_sint", "col_temp_sint", "col_fluor_sint"]
H_CTD = ["col_fecha_sint", "col_lat_sint", "col_lon_sint",
         "col_prof_sint", "col_temp_sint"]

ROLES_VACIOS = {"fecha": None, "hora": None, "latitud": None,
                "longitud": None, "estacion": None, "profundidad": None}


def config_base(roles=None, tokens=("fluor",), extensiones=None, allowlist=()) -> dict:
    return {
        "fuente": {"variable_entorno": ENV, "formato": "xlsx"},
        "hojas_requeridas": ["BOTELLAS", "CTD"],
        "periodo_esperado": {"inicio": "2026-02-16", "fin": "2026-04-03"},
        "column_roles": roles or {"BOTELLAS": dict(ROLES_VACIOS), "CTD": dict(ROLES_VACIOS)},
        "fluorescencia": {"tokens_encabezado": list(tokens)},
        "proteccion_datos": {
            "extensiones": list(extensiones or [".zip", ".xlsx", ".xls", ".csv", ".pdf"]),
            "allowlist": list(allowlist),
        },
    }


def roles_completos() -> dict:
    return {
        "BOTELLAS": {"fecha": "col_fecha_sint", "hora": "col_hora_sint",
                     "latitud": "col_lat_sint", "longitud": "col_lon_sint",
                     "estacion": "col_estacion_sint", "profundidad": None},
        "CTD": {"fecha": "col_fecha_sint", "hora": "col_fecha_sint",
                "latitud": "col_lat_sint", "longitud": "col_lon_sint",
                "estacion": None, "profundidad": "col_prof_sint"},
    }


def df_bot(fechas=None, horas=None) -> pd.DataFrame:
    if fechas is None:
        fechas = ["2026-02-20", "2026-03-01", "2026-03-14"]
    n = len(fechas)
    if horas is None:
        horas = [None] * n
    return pd.DataFrame({
        "col_fecha_sint": [pd.Timestamp(f) if f else None for f in fechas],
        "col_hora_sint": horas,
        "col_lat_sint": [-12.5, -12.6, -12.5][:n],
        "col_lon_sint": [-76.9, -77.0, -76.9][:n],
        "col_estacion_sint": ["E1", "E2", "E1"][:n],
        "col_temp_sint": [20.1, None, 19.8][:n],
        "col_fluor_sint": [0.5, 0.7, None][:n],
    })


def df_ctd() -> pd.DataFrame:
    return pd.DataFrame({
        "col_fecha_sint": [pd.Timestamp("2026-03-02")] * 4,
        "col_lat_sint": [-12.7] * 4,
        "col_lon_sint": [-77.1] * 4,
        "col_prof_sint": [0.5, 5.0, 10.0, 20.0],
        "col_temp_sint": [20.0, 19.5, 18.2, 16.9],
    })


def escribir(tmp_path: Path, hojas: dict, nombre="libro_sintetico.xlsx") -> Path:
    ruta = tmp_path / nombre
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        for hoja, df in hojas.items():
            df.to_excel(w, sheet_name=hoja, index=False)
    return ruta


def libro_estandar(tmp_path: Path, bot=None, ctd=None, extra=None) -> Path:
    hojas = {"BOTELLAS": bot if bot is not None else df_bot(),
             "CTD": ctd if ctd is not None else df_ctd()}
    if extra:
        hojas.update(extra)
    return escribir(tmp_path, hojas)


def payload(df: pd.DataFrame, headers=None) -> vi.SheetPayload:
    return vi.SheetPayload(raw_headers=tuple(headers or df.columns), frame=df)


def hoja(nombre: str) -> callable:
    return lambda rep: next(s for s in rep.sheets if s.name == nombre)


# --------------------------------------------------------------------------
# 1. La ruta llega SOLO por la variable de entorno.
# --------------------------------------------------------------------------
def test_1_ruta_solo_por_variable_de_entorno(tmp_path):
    cfg = config_base()

    with pytest.raises(vi.SourceNotDeclaredError):
        vi.resolve_source_path(cfg, env={})
    with pytest.raises(vi.SourceNotDeclaredError):
        vi.resolve_source_path(cfg, env={ENV: "   "})
    with pytest.raises(vi.SourceNotFoundError):
        vi.resolve_source_path(cfg, env={ENV: str(tmp_path / "no_existe.xlsx")})

    real = libro_estandar(tmp_path)
    assert vi.resolve_source_path(cfg, env={ENV: str(real)}) == real
    assert "path" not in py_inspect.signature(vi.resolve_source_path).parameters


# --------------------------------------------------------------------------
# 2. Sin rutas reales en el codigo ni en el YAML del repositorio.
# --------------------------------------------------------------------------
def test_2_sin_rutas_reales():
    fuente = py_inspect.getsource(vi)
    for patron in ("/home/", "/mnt/", "C:\\", "~/Documents", "IMARPE.zip", "2602-04"):
        assert patron not in fuente, "posible ruta o dato real en el codigo: %r" % patron

    texto = Path("config/imarpe_source.yaml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(texto)
    assert cfg["fuente"]["variable_entorno"] == ENV
    assert cfg["fuente"].get("ruta") is None
    for patron in ("/home/", "/mnt/", "C:\\"):
        assert patron not in texto, "posible ruta real en el YAML: %r" % patron


# --------------------------------------------------------------------------
# 3. Sin red.
# --------------------------------------------------------------------------
def test_3_sin_red():
    fuente = py_inspect.getsource(vi)
    for prohibido in ("import requests", "import urllib", "import http",
                      "urlopen", "socket.", "http://", "https://"):
        assert prohibido not in fuente, "el inspector no debe tocar la red: %r" % prohibido


# --------------------------------------------------------------------------
# 4. MINIMIZACION: una tercera hoja NUNCA se materializa.
#    El lector falla a proposito si alguien intenta abrirla.
# --------------------------------------------------------------------------
def test_4_minimizacion_no_abre_hoja_ajena(tmp_path):
    cfg = config_base()
    pedidas = []

    def lister(_):
        return ("BOTELLAS", "CTD", "HOJA_PROHIBIDA")

    def reader(_, sheets):
        pedidas.append(tuple(sheets))
        if "HOJA_PROHIBIDA" in sheets:
            raise AssertionError("se intento abrir una hoja que no corresponde leer")
        return {"BOTELLAS": payload(df_bot()), "CTD": payload(df_ctd())}

    rep = vi.inspect_workbook(tmp_path / "x.xlsx", cfg, lister=lister, reader=reader)

    assert pedidas == [("BOTELLAS", "CTD")], "solo se piden las hojas requeridas"
    assert rep.sheet_names == ("BOTELLAS", "CTD", "HOJA_PROHIBIDA"), "listar si ve las tres"
    assert rep.materialized_sheets == ("BOTELLAS", "CTD")
    assert {s.name for s in rep.sheets} == {"BOTELLAS", "CTD"}


# --------------------------------------------------------------------------
# 5. MINIMIZACION con archivo real de tres hojas y el lector real.
# --------------------------------------------------------------------------
def test_5_minimizacion_con_archivo_real(tmp_path):
    cfg = config_base()
    extra = {"HOJA_AJENA": pd.DataFrame({"otra_col_sint": [1, 2, 3]})}
    ruta = libro_estandar(tmp_path, extra=extra)

    assert vi.list_sheet_names(ruta) == ("BOTELLAS", "CTD", "HOJA_AJENA")

    cargadas = vi.read_sheets(ruta, ("BOTELLAS", "CTD"))
    assert set(cargadas) == {"BOTELLAS", "CTD"}, "la hoja ajena no se materializa"

    rep = vi.inspect_workbook(ruta, cfg)
    assert rep.materialized_sheets == ("BOTELLAS", "CTD")
    assert len(rep.sheets) == 2


# --------------------------------------------------------------------------
# 6. Encabezados EXACTOS, sin pasar por DataFrame.columns.
# --------------------------------------------------------------------------
def test_6_encabezados_exactos(tmp_path):
    cfg = config_base()
    ruta = libro_estandar(tmp_path)

    b = hoja("BOTELLAS")(vi.inspect_workbook(ruta, cfg))
    assert b.headers == tuple(H_BOT)

    # Se conservan tal cual: no se recortan espacios ni se normaliza.
    crudos = ("  con espacios  ", "MAYUS", "con.punto")
    assert vi.exact_headers("X", crudos) == crudos

    # Escalares no textuales se aceptan convertidos, sin alterar el resto.
    assert vi.exact_headers("X", ("a", 7, 2.5)) == ("a", "7", "2.5")


# --------------------------------------------------------------------------
# 7. Encabezados duplicados: error, sin sufijos ni renombrado.
#    pandas SI los renombraria, y por eso no se usa DataFrame.columns.
# --------------------------------------------------------------------------
def test_7_encabezados_duplicados(tmp_path):
    with pytest.raises(vi.UnreadableSchemaError) as exc:
        vi.exact_headers("BOTELLAS", ("a", "b", "a"))
    assert "duplicados" in str(exc.value) and "sufijo" in str(exc.value)

    # Demostracion de por que no basta con DataFrame.columns.
    ruta = tmp_path / "dup.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOTELLAS"
    ws.append(["dupe", "dupe"])
    ws.append([1, 2])
    wb.create_sheet("CTD").append(["c"])
    wb.save(ruta)

    marco = pd.ExcelFile(ruta, engine="openpyxl").parse(sheet_name="BOTELLAS")
    assert list(marco.columns) != ["dupe", "dupe"], "pandas renombra: por eso no se usa"

    with pytest.raises(vi.UnreadableSchemaError):
        vi.inspect_workbook(ruta, config_base())


# --------------------------------------------------------------------------
# 8. Encabezados vacios, en blanco o no interpretables.
# --------------------------------------------------------------------------
def test_8_encabezados_invalidos():
    with pytest.raises(vi.UnreadableSchemaError) as e1:
        vi.exact_headers("X", ("a", None, "c"))
    assert "vacio" in str(e1.value) and "posicion 2" in str(e1.value)

    with pytest.raises(vi.UnreadableSchemaError) as e2:
        vi.exact_headers("X", ("a", "   ", "c"))
    assert "blanco" in str(e2.value)

    with pytest.raises(vi.UnreadableSchemaError) as e3:
        vi.exact_headers("X", ("a", ["lista"], "c"))
    assert "no interpretable" in str(e3.value)

    with pytest.raises(vi.UnreadableSchemaError):
        vi.exact_headers("X", ())


# --------------------------------------------------------------------------
# 9. PROHIBIDO ADIVINAR: una sola columna datetime NO se toma como fecha.
# --------------------------------------------------------------------------
def test_9_no_se_adivina_el_rol_fecha(tmp_path):
    cfg = config_base()  # roles vacios
    ruta = libro_estandar(tmp_path, bot=df_bot(), ctd=df_ctd())

    c = hoja("CTD")(vi.inspect_workbook(ruta, cfg))

    assert "col_fecha_sint" in c.datetime_candidate_headers, "se informa como CANDIDATO"
    assert c.date_role is None
    assert c.date_min is None and c.date_max is None
    assert c.n_out_of_period is None, "sin rol declarado no hay cuarentena calculada"
    assert c.n_unparseable_dates is None
    assert any("rango_de_fechas" in m and "column_roles.CTD.fecha" in m
               for m in c.unresolved_metrics)
    assert any("candidatos fecha-hora observados" in m for m in c.unresolved_metrics)


# --------------------------------------------------------------------------
# 10. Con rol declarado si se calculan rango y cuarentena.
# --------------------------------------------------------------------------
def test_10_metricas_oficiales_con_rol(tmp_path):
    cfg = config_base(roles=roles_completos())
    fechas = ["2026-02-20", "2023-02-23", "2026-03-14"]  # una anomalia, como la real
    ruta = libro_estandar(tmp_path, bot=df_bot(fechas=fechas))

    b = hoja("BOTELLAS")(vi.inspect_workbook(ruta, cfg))

    assert b.date_role == "col_fecha_sint"
    assert b.n_out_of_period == 1
    assert b.date_min == "2023-02-23", "la fecha anomala NO se corrige ni se excluye"
    assert b.n_unique_coordinates == 2
    assert b.n_unique_stations == 2


# --------------------------------------------------------------------------
# 11. Rol HORA en columna SEPARADA.
# --------------------------------------------------------------------------
def test_11_rol_hora_en_columna_separada(tmp_path):
    cfg = config_base(roles=roles_completos())

    horas = [dt.time(7, 30), dt.time(13, 0), dt.time(19, 15)]
    con_hora = escribir(tmp_path, {"BOTELLAS": df_bot(horas=horas), "CTD": df_ctd()},
                        "con_hora.xlsx")
    b = hoja("BOTELLAS")(vi.inspect_workbook(con_hora, cfg))
    assert b.time_role == "col_hora_sint"
    assert b.time_source == "columna_hora_separada"
    assert b.has_time_component is True

    medianoche = [dt.time(0, 0)] * 3
    sin_hora = escribir(tmp_path, {"BOTELLAS": df_bot(horas=medianoche), "CTD": df_ctd()},
                        "medianoche.xlsx")
    b2 = hoja("BOTELLAS")(vi.inspect_workbook(sin_hora, cfg))
    assert b2.has_time_component is False, "todo a medianoche equivale a sin hora"


# --------------------------------------------------------------------------
# 12. Rol HORA en la MISMA columna que fecha: hay que declararlo en ambos.
# --------------------------------------------------------------------------
def test_12_hora_en_la_misma_columna(tmp_path):
    roles = roles_completos()
    roles["BOTELLAS"]["hora"] = "col_fecha_sint"  # misma columna
    cfg = config_base(roles=roles)

    bot = df_bot()
    bot["col_fecha_sint"] = [pd.Timestamp("2026-02-20 07:30"),
                             pd.Timestamp("2026-03-01 13:00"),
                             pd.Timestamp("2026-03-14 19:15")]
    b = hoja("BOTELLAS")(vi.inspect_workbook(
        escribir(tmp_path, {"BOTELLAS": bot, "CTD": df_ctd()}, "misma.xlsx"), cfg))

    assert b.time_role == "col_fecha_sint"
    assert b.time_source == "misma_columna_que_fecha"
    assert b.has_time_component is True

    # Declarar el MISMO encabezado en fecha y hora es lo que activa la lectura.
    assert cfg["column_roles"]["BOTELLAS"]["fecha"] == cfg["column_roles"]["BOTELLAS"]["hora"]


# --------------------------------------------------------------------------
# 13. Sin rol fecha NI hora: la presencia de hora queda NO RESUELTA.
# --------------------------------------------------------------------------
def test_13_hora_no_resuelta_sin_roles(tmp_path):
    cfg = config_base()
    b = hoja("BOTELLAS")(vi.inspect_workbook(libro_estandar(tmp_path), cfg))

    assert b.has_time_component is None
    assert b.time_source is None
    assert b.n_unparseable_times is None
    assert any("presencia_de_hora" in m for m in b.unresolved_metrics)


# --------------------------------------------------------------------------
# 14. Rol declarado cuya columna NO existe -> UnreadableSchemaError.
#     Se comprueban los SEIS roles.
# --------------------------------------------------------------------------
def test_14_rol_inexistente_es_error(tmp_path):
    for rol in ("fecha", "hora", "latitud", "longitud", "estacion", "profundidad"):
        roles = {"BOTELLAS": dict(ROLES_VACIOS), "CTD": dict(ROLES_VACIOS)}
        roles["BOTELLAS"][rol] = "columna_que_no_existe_sint"
        cfg = config_base(roles=roles)
        with pytest.raises(vi.UnreadableSchemaError) as exc:
            vi.inspect_workbook(libro_estandar(tmp_path), cfg)
        assert "columna_que_no_existe_sint" in str(exc.value)
        assert "parecida" in str(exc.value), "no debe degradarse ni buscar sustituto"


# --------------------------------------------------------------------------
# 15. Fechas no interpretables: se CUENTAN, no se muestran ni se corrigen.
# --------------------------------------------------------------------------
def test_15_fechas_no_interpretables(tmp_path):
    cfg = config_base(roles=roles_completos())
    bot = df_bot()
    bot["col_fecha_sint"] = ["2026-02-20", "no-es-fecha-sint", None]

    rep = vi.inspect_workbook(
        escribir(tmp_path, {"BOTELLAS": bot, "CTD": df_ctd()}, "malas.xlsx"), cfg)
    b = hoja("BOTELLAS")(rep)

    assert b.n_unparseable_dates == 1, "una presente pero no interpretable"
    assert b.missing_counts["col_fecha_sint"] == 1, "el faltante sigue siendo faltante"
    assert b.date_min == "2026-02-20" and b.date_max == "2026-02-20"

    texto = vi.format_report(rep)
    assert "no-es-fecha-sint" not in texto, "no se muestra el valor problematico"

    fuente = py_inspect.getsource(vi)
    for prohibido in ("fillna", ".interpolate(", "ffill", "bfill", ".replace("):
        assert prohibido not in fuente, "el inspector no debe corregir ni rellenar: %r" % prohibido


# --------------------------------------------------------------------------
# 16. Fluorescencia declarada NO CUANTITATIVA.
# --------------------------------------------------------------------------
def test_16_fluorescencia_no_cuantitativa(tmp_path):
    cfg = config_base()
    rep = vi.inspect_workbook(libro_estandar(tmp_path), cfg)

    b = hoja("BOTELLAS")(rep)
    assert b.fluorescence_headers == ("col_fluor_sint",)
    d = rep.fluorescence_declaration.lower()
    assert "no cuantitativa" in d and "no es clorofila calibrada" in d
    assert "NO CUANTITATIVA" in vi.format_report(rep)

    assert hoja("CTD")(rep).fluorescence_headers == (), "no se inventa lo que no existe"


# --------------------------------------------------------------------------
# 17. El informe NO expone contenido.
# --------------------------------------------------------------------------
def test_17_el_informe_no_expone_contenido(tmp_path):
    cfg = config_base(roles=roles_completos())
    texto = vi.format_report(vi.inspect_workbook(libro_estandar(tmp_path), cfg))

    for valor in ("-12.5", "-76.9", "-12.6", "-77.0", "-12.7", "-77.1",
                  "20.1", "19.8", "18.2", "16.9", "0.5", "0.7", "E1", "E2"):
        assert valor not in texto, "el informe expone contenido: %r" % valor
    assert "col_fecha_sint" in texto, "los encabezados si deben aparecer"
    assert "2026-02-20" in texto, "el rango de fechas si fue solicitado"


# --------------------------------------------------------------------------
# 18. Falta una hoja requerida -> error claro, sin sustituir por parecida.
# --------------------------------------------------------------------------
def test_18_falta_hoja_requerida(tmp_path):
    cfg = config_base()
    ruta = escribir(tmp_path, {"BOTELLAS": df_bot(), "CTD_2026": df_ctd()}, "sin_ctd.xlsx")

    with pytest.raises(vi.MissingSheetError) as exc:
        vi.inspect_workbook(ruta, cfg)
    assert "CTD" in str(exc.value) and "parecido" in str(exc.value)


# --------------------------------------------------------------------------
# 19. Libro ilegible y desajuste encabezado/cuerpo.
# --------------------------------------------------------------------------
def test_19_esquema_ilegible(tmp_path):
    cfg = config_base()

    falso = tmp_path / "no_es_excel.xlsx"
    falso.write_text("esto no es un libro", encoding="utf-8")
    with pytest.raises(vi.UnreadableSchemaError):
        vi.inspect_workbook(falso, cfg)

    def lister(_):
        return ("BOTELLAS", "CTD")

    def reader(_, sheets):
        return {"BOTELLAS": vi.SheetPayload(raw_headers=("a", "b", "c"),
                                            frame=pd.DataFrame({"a": [1], "b": [2]})),
                "CTD": payload(df_ctd())}

    with pytest.raises(vi.UnreadableSchemaError) as exc:
        vi.inspect_workbook(tmp_path / "x.xlsx", cfg, lister=lister, reader=reader)
    assert "encabezados" in str(exc.value) and "columnas" in str(exc.value)


# --------------------------------------------------------------------------
# 20. GOBERNANZA: la extension basta; el nombre es irrelevante.
# --------------------------------------------------------------------------
def test_20_deteccion_por_extension_no_por_nombre():
    rastreados = [
        "README.md",
        "ingestion/fetch_sst.py",
        "data/IMARPE.zip",
        "docs/crucero_2602.xlsx",          # sin la palabra imarpe
        "notas/OFICIO.PDF",                # mayusculas
        "otros/tabla_cualquiera.csv",      # sin la palabra imarpe
        "validation/inspect_imarpe.py",
        "config/imarpe_source.yaml",
    ]

    hallados = vi.find_tracked_restricted_files(rastreados)

    assert "docs/crucero_2602.xlsx" in hallados, "la extension basta, el nombre no importa"
    assert "otros/tabla_cualquiera.csv" in hallados
    assert "notas/OFICIO.PDF" in hallados, "deteccion insensible a mayusculas"
    assert "data/IMARPE.zip" in hallados
    assert "validation/inspect_imarpe.py" not in hallados, "el codigo no es dato"
    assert "config/imarpe_source.yaml" not in hallados, "la declaracion no es dato"
    assert hallados == tuple(sorted(hallados)), "salida determinista"


# --------------------------------------------------------------------------
# 21. Allowlist explicita, vacia por defecto.
# --------------------------------------------------------------------------
def test_21_allowlist_explicita():
    rastreados = ["docs/plantilla_publica.csv"]

    assert vi.find_tracked_restricted_files(rastreados) == ("docs/plantilla_publica.csv",)
    assert vi.find_tracked_restricted_files(
        rastreados, allowlist=("docs/plantilla_publica.csv",)) == ()
    assert vi.find_tracked_restricted_files(
        rastreados, allowlist=("DOCS/PLANTILLA_PUBLICA.CSV",)) == (), "allowlist insensible"

    real = yaml.safe_load(Path("config/imarpe_source.yaml").read_text(encoding="utf-8"))
    assert real["proteccion_datos"]["allowlist"] == [], "vacia por defecto"


# --------------------------------------------------------------------------
# 22. Si git falla, la gobernanza FALLA; nunca aparenta estar limpia.
# --------------------------------------------------------------------------
def test_22_git_indisponible_falla(monkeypatch, tmp_path):
    import subprocess as sp

    def sin_git(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(vi.subprocess, "run", sin_git)
    with pytest.raises(vi.GovernanceCheckError) as e1:
        vi.git_tracked_files(tmp_path)
    assert "NO pudo realizarse" in str(e1.value)

    class Fallo:
        returncode = 128
        stdout = ""
        stderr = "fatal: not a git repository"

    monkeypatch.setattr(vi.subprocess, "run", lambda *a, **k: Fallo())
    with pytest.raises(vi.GovernanceCheckError) as e2:
        vi.git_tracked_files(tmp_path)
    assert "128" in str(e2.value)

    with pytest.raises(vi.GovernanceCheckError):
        vi.assert_no_restricted_tracked(cfg=config_base(), repo_root=tmp_path)


# --------------------------------------------------------------------------
# 23. La comprobacion de gobernanza falla ante una fuga y menciona gitignore.
# --------------------------------------------------------------------------
def test_23_gobernanza_falla_ante_fuga():
    cfg = config_base()

    assert vi.assert_no_restricted_tracked(tracked=["README.md", "ingestion/x.py"], cfg=cfg) == ()

    with pytest.raises(vi.GovernanceCheckError) as exc:
        vi.assert_no_restricted_tracked(tracked=["cualquiera/archivo.xlsx"], cfg=cfg)
    mensaje = str(exc.value)
    assert "FUGA DE DATOS RESTRINGIDOS" in mensaje
    assert "Codespaces" in mensaje, "debe recordar que gitignore no autoriza transferir"


# --------------------------------------------------------------------------
# 24. La configuracion real del repositorio es utilizable y sigue sin roles.
# --------------------------------------------------------------------------
def test_24_configuracion_real_utilizable():
    cfg = vi.load_config("config/imarpe_source.yaml")

    assert cfg["hojas_requeridas"] == ["BOTELLAS", "CTD"]
    assert cfg["fuente"]["variable_entorno"] == ENV
    assert cfg["periodo_esperado"]["inicio"] == "2026-02-16"
    assert cfg["periodo_esperado"]["fin"] == "2026-04-03"
    roles = cfg["column_roles"]
    assert set(roles) == {"BOTELLAS", "CTD"}
    assert all(v is None for h in roles.values() for v in h.values()), \
        "los roles deben quedar sin declarar hasta la Fase 1B"
    assert "fluor" in cfg["fluorescencia"]["tokens_encabezado"]
    assert set(cfg["proteccion_datos"]["extensiones"]) >= {".zip", ".xlsx", ".csv", ".pdf"}

    with pytest.raises(vi.ImarpeInspectionError):
        vi.load_config("config/no_existe_esta_declaracion.yaml")


# --------------------------------------------------------------------------
# 25. Rol PROFUNDIDAD: sin declarar queda no resuelto; declarado se calcula.
# --------------------------------------------------------------------------
def test_25_rol_profundidad(tmp_path):
    sin_roles = hoja("CTD")(vi.inspect_workbook(libro_estandar(tmp_path), config_base()))
    assert sin_roles.depth_role is None
    assert sin_roles.n_unique_depths is None
    assert sin_roles.n_non_numeric_depths is None
    assert any("niveles_de_profundidad" in m and "column_roles.CTD.profundidad" in m
               for m in sin_roles.unresolved_metrics)

    con_roles = hoja("CTD")(vi.inspect_workbook(
        libro_estandar(tmp_path), config_base(roles=roles_completos())))
    assert con_roles.depth_role == "col_prof_sint"
    assert con_roles.n_unique_depths == 4, "cuatro niveles distintos en el perfil sintetico"
    assert con_roles.n_non_numeric_depths == 0
    assert not any("niveles_de_profundidad" in m for m in con_roles.unresolved_metrics)


# --------------------------------------------------------------------------
# 26. Profundidades no numericas: se CUENTAN, no se muestran ni se corrigen.
# --------------------------------------------------------------------------
def test_26_profundidades_no_numericas(tmp_path):
    ctd = df_ctd()
    ctd["col_prof_sint"] = [0.5, "no-es-profundidad-sint", 10.0, None]
    ruta = escribir(tmp_path, {"BOTELLAS": df_bot(), "CTD": ctd}, "prof_malas.xlsx")

    rep = vi.inspect_workbook(ruta, config_base(roles=roles_completos()))
    c = hoja("CTD")(rep)

    assert c.n_non_numeric_depths == 1
    assert c.n_unique_depths == 2, "solo los numericos cuentan como niveles"
    assert c.missing_counts["col_prof_sint"] == 1, "el faltante sigue siendo faltante"
    assert "no-es-profundidad-sint" not in vi.format_report(rep)


# --------------------------------------------------------------------------
# 27. SIN FALLBACK: declarar fecha no implica conocer la hora.
# --------------------------------------------------------------------------
def test_27_sin_fallback_de_fecha_a_hora(tmp_path):
    roles = {"BOTELLAS": dict(ROLES_VACIOS), "CTD": dict(ROLES_VACIOS)}
    roles["BOTELLAS"]["fecha"] = "col_fecha_sint"   # fecha si, hora NO
    cfg = config_base(roles=roles)

    bot = df_bot()
    bot["col_fecha_sint"] = [pd.Timestamp("2026-02-20 07:30"),
                             pd.Timestamp("2026-03-01 13:00"),
                             pd.Timestamp("2026-03-14 19:15")]
    b = hoja("BOTELLAS")(vi.inspect_workbook(
        escribir(tmp_path, {"BOTELLAS": bot, "CTD": df_ctd()}, "solo_fecha.xlsx"), cfg))

    assert b.date_role == "col_fecha_sint", "la fecha si esta resuelta"
    assert b.time_role is None
    assert b.time_source is None
    assert b.has_time_component is None, "aunque la columna traiga hora, no se deduce"
    assert b.n_unparseable_times is None
    assert any("declare ese mismo encabezado tambien en .hora" in m
               for m in b.unresolved_metrics)


# --------------------------------------------------------------------------
# 28. COMPUERTA: Codespaces bloquea la inspeccion real.
# --------------------------------------------------------------------------
def test_28_compuerta_codespaces(tmp_path):
    fuera = tmp_path / "fuera_del_repo.xlsx"
    fuera.write_text("marcador", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(vi.ExecutionEnvironmentError) as exc:
        vi.assert_execution_environment_allowed(env={"CODESPACES": "true"})
    assert "CODESPACES" in str(exc.value)
    assert "restriccion de transferencia" in str(exc.value)

    with pytest.raises(vi.ExecutionEnvironmentError):
        vi.assert_execution_environment_allowed(env={"CODESPACES": "TRUE"})

    # Sin la variable, o con otro valor, el entorno no bloquea.
    vi.assert_execution_environment_allowed(fuera, env={}, repo_root=repo)
    vi.assert_execution_environment_allowed(fuera, env={"CODESPACES": "false"}, repo_root=repo)


# --------------------------------------------------------------------------
# 29. COMPUERTA: el Excel dentro del repositorio se rechaza aunque no este
#     rastreado por Git, aunque .gitignore lo oculte y AUNQUE el comando se
#     lance desde otro directorio.
# --------------------------------------------------------------------------
def test_29_compuerta_archivo_dentro_del_repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "datos").mkdir(parents=True)
    (repo / "subdir").mkdir()
    dentro = repo / "datos" / "entrega.xlsx"
    dentro.write_text("marcador", encoding="utf-8")
    (repo / ".gitignore").write_text("*.xlsx" + chr(10) + "datos/" + chr(10), encoding="utf-8")

    # No esta rastreado: la comprobacion de Git no lo veria.
    assert vi.find_tracked_restricted_files([]) == ()

    # Con la raiz declarada explicitamente, la compuerta dispara.
    with pytest.raises(vi.ExecutionEnvironmentError) as exc:
        vi.assert_execution_environment_allowed(dentro, env={}, repo_root=repo)
    mensaje = str(exc.value)
    assert "DENTRO del arbol del repositorio" in mensaje
    assert "ignorado no es ausente" in mensaje.lower()
    assert str(dentro) not in mensaje, "no se imprime la ruta"

    # --- INDEPENDENCIA DEL DIRECTORIO DE TRABAJO ---
    # El comando se lanza desde un subdirectorio del repositorio simulado y el
    # Excel esta en OTRA carpeta del mismo repositorio.
    monkeypatch.chdir(repo / "subdir")
    monkeypatch.setattr(vi, "REPO_ROOT", repo)

    # Demostracion del fallo que se corrige: si la raiz fuera el cwd, el
    # archivo quedaria "fuera" y la compuerta NO dispararia.
    vi.assert_execution_environment_allowed(dentro, env={}, repo_root=Path.cwd())

    # Con REPO_ROOT y SIN pasar repo_root, sigue disparando.
    with pytest.raises(vi.ExecutionEnvironmentError) as exc2:
        vi.assert_execution_environment_allowed(dentro, env={})
    assert "DENTRO del arbol del repositorio" in str(exc2.value)

    # Un archivo realmente fuera del repositorio sigue autorizado.
    fuera = tmp_path / "afuera" / "entrega.xlsx"
    fuera.parent.mkdir()
    fuera.write_text("marcador", encoding="utf-8")
    vi.assert_execution_environment_allowed(fuera, env={})


# --------------------------------------------------------------------------
# 30. Las pruebas sinteticas SI pueden correr en Codespaces.
# --------------------------------------------------------------------------
def test_30_sinteticas_no_bloqueadas_en_codespaces(tmp_path, monkeypatch):
    monkeypatch.setenv("CODESPACES", "true")

    # La inspeccion de un libro SINTETICO no pasa por la compuerta.
    rep = vi.inspect_workbook(libro_estandar(tmp_path), config_base(roles=roles_completos()))
    assert len(rep.sheets) == 2

    # El camino real si queda bloqueado.
    with pytest.raises(vi.ExecutionEnvironmentError):
        vi.assert_execution_environment_allowed()
    assert vi.main("config/imarpe_source.yaml") == 1, "main devuelve error, no informe"
