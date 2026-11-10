"""The registered OpenBattery UI must be self-contained and independently owned."""
from pathlib import Path
import re

from custom_components.omnibattery.openbattery_brand import PANEL_ELEMENT, PANEL_MODULE


FRONTEND = Path(__file__).resolve().parents[1] / "custom_components/omnibattery/frontend"


def test_registered_panel_and_assets_ship_inside_owned_directory():
    panel = FRONTEND / PANEL_MODULE
    assert panel.is_file()
    source = panel.read_text(encoding="utf-8")
    assert f'customElements.define("{PANEL_ELEMENT}"' in source
    assert PANEL_ELEMENT != "marstek-venus-panel"
    assert "assets/openbattery-icon.png" in source
    assert 'new URL("assets/", import.meta.url)' in source
    for filename in ("openbattery-icon.png", "home-scene-day.png", "home-scene-night.png",
                     "home-scene-day_2.png", "home-scene-night_2.png"):
        assert (panel.parent / "assets" / filename).is_file()


def test_active_panel_retains_fork_features_and_upstream_reference_is_separate():
    active = (FRONTEND / PANEL_MODULE).read_text(encoding="utf-8")
    upstream = (FRONTEND / "marstek-panel.js").read_text(encoding="utf-8")
    assert "_phaseMonitoringState()" in active
    assert "monthly_full_charge_source" in active
    assert 'customElements.define("marstek-venus-panel"' in upstream


def test_all_ui_regressions_target_the_active_panel():
    tests = Path(__file__).parent
    for path in tests.glob("test_*.py"):
        if path == Path(__file__):
            continue
        source = path.read_text(encoding="utf-8")
        assert not re.search(r'frontend(?:/|" / ")marstek-panel\.js', source), path.name
