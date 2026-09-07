"""Contrato estático de la aplicación web de PredictaMAR Litoral.

La suite no abre un navegador ni consulta fuentes reales. Comprueba que la PWA
consume una muestra compatible con ``environmental_snapshot_v1``, conserva el
alcance espacial y se identifica de forma visible como demostración sintética.
"""

from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
INDEX = DIST / "index.html"
FIXTURE = DIST / "fixtures" / "environmental_snapshot.sample.json"

VARIABLE_IDS = {
    "sst",
    "oleaje",
    "clorofila",
    "salinidad",
    "sst_observed_ostia",
    "thermal_front",
    "temperature_10m",
    "delta_sst_t10",
    "surface_currents",
    "batimetria",
}


class _AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []
        self.ids = set()
        self.labels_for = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "label" and values.get("for"):
            self.labels_for.add(values["for"])
        if tag == "link" and values.get("href"):
            self.references.append(values["href"])
        if tag == "script" and values.get("src"):
            self.references.append(values["src"])


def _load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_application_entrypoint_references_only_existing_local_assets():
    parser = _AssetParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))

    local_references = [
        reference
        for reference in parser.references
        if not reference.startswith(("http://", "https://", "#"))
    ]
    assert local_references
    assert all((DIST / reference.removeprefix("./")).is_file() for reference in local_references)

    hosting = json.loads((ROOT / ".openai" / "hosting.json").read_text(encoding="utf-8"))
    assert hosting["static"]["directory"] == "dist"


def test_application_exposes_labeled_controls_and_explicit_ui_states():
    parser = _AssetParser()
    parser.feed(INDEX.read_text(encoding="utf-8"))

    assert {"location", "target-date"} <= parser.labels_for
    assert {
        "snapshot-form",
        "app-status",
        "dashboard",
        "empty-state",
        "safety-card",
        "variable-groups",
        "offline-banner",
    } <= parser.ids


def test_sample_matches_the_environmental_snapshot_v1_contract():
    document = _load_fixture()

    assert document["schema_version"] == "environmental_snapshot_v1"
    assert set(document["variables"]) == VARIABLE_IDS
    assert document["counts"] == {"available": 10, "no_data": 0, "error": 0, "total": 10}
    assert document["spatial_context"]["operational_range_max_km"] == 10.0
    assert document["spatial_context"]["operational_range_basis"] == "distance_offshore_from_coastline"
    assert document["spatial_context"]["operational_range_is_radius_from_request_point"] is False
    assert document["spatial_context"]["field_half_width_deg"] == 0.15
    assert document["spatial_context"]["field_is_operational_domain"] is False

    scopes = {name: result["spatial_scope"] for name, result in document["variables"].items()}
    assert scopes["sst_observed_ostia"] == "regional_field"
    assert scopes["thermal_front"] == "regional_field"
    assert scopes["oleaje"] == "regional_maximum"
    assert all(
        scope == "point"
        for name, scope in scopes.items()
        if name not in {"sst_observed_ostia", "thermal_front", "oleaje"}
    )


def test_sample_cannot_activate_prediction_or_hide_its_synthetic_origin():
    document = _load_fixture()
    html = INDEX.read_text(encoding="utf-8").lower()

    assert "datos simulados" in html
    assert "no calcula probabilidad de pesca" in html
    assert "no constituye autorización" in document["safety"]["not_authorization_notice"].lower()
    assert all(
        result["governance"]["predictively_valid"] is not True
        for result in document["variables"].values()
    )
    assert all(
        "synthetic" in result["payload"]["data_scope"]
        for result in document["variables"].values()
    )


def test_manifest_and_service_worker_make_the_static_shell_installable():
    manifest = json.loads((DIST / "manifest.webmanifest").read_text(encoding="utf-8"))
    worker = (DIST / "service-worker.js").read_text(encoding="utf-8")

    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    assert manifest["icons"]
    assert all((DIST / icon["src"].removeprefix("./")).is_file() for icon in manifest["icons"])
    for asset in (
        "./index.html",
        "./styles.css",
        "./app-model.js",
        "./app.js",
        "./fixtures/environmental_snapshot.sample.json",
    ):
        assert asset in worker


def test_javascript_modules_have_valid_syntax():
    node = shutil.which("node")
    assert node is not None, "Node.js es necesario para validar los módulos de la PWA."

    for source in (DIST / "app-model.js", DIST / "app.js", DIST / "service-worker.js"):
        result = subprocess.run(
            [node, "--input-type=module", "--check"],
            input=source.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
