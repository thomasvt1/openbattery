"""Execute the shipped phase monitor model and DOM patch in Node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components/omnibattery/frontend/openbattery/panel.js"
HARNESS = r"""
(async () => {
const fs = require('node:fs');
const vm = require('node:vm');
let Panel;
let clock = Date.now();
const timers = new Map();
let timerId = 0;
const context = vm.createContext({
  HTMLElement: class {},
  customElements: { get() {}, define(name, cls) { Panel = cls; } },
  Date: class extends Date { static now() {return clock;} },
  setTimeout(fn, delay) {timers.set(++timerId, {fn, delay}); return timerId;},
  clearTimeout(id) {timers.delete(id);},
});
const runtime = new vm.SourceTextModule(fs.readFileSync(process.argv[1], 'utf8'), { context });
await runtime.link(() => { throw new Error('Unexpected external import'); });
await runtime.evaluate();
const scenario = JSON.parse(fs.readFileSync(0, 'utf8'));
const panel = Object.create(Panel.prototype);
const id = 'sensor.renamed_phase_status';
const attrs = {
  protection_enabled: true,
  monitoring_updated_at: new Date(Date.now() - (scenario.age || 0)*1000).toISOString(),
  ...scenario.attrs,
};
panel._panelConfig = {};
panel.isConnected = true;
panel._view = 'resumen';
panel._hass = {
  states: scenario.missing ? {} : {
    [id]: {state: scenario.state || 'active', attributes: attrs},
    'sensor.l1': {state: '0', attributes: {}},
  },
  entities: {[id]: {entity_id: id, platform: 'omnibattery', translation_key: 'three_phase_protection_status'}},
  devices: {}, locale: {language: scenario.language || 'en'},
};
function node() {return {
  style: {}, dataset: {}, attributes: {}, textContent: '', hidden: false,
  classList: {add() {}, remove() {}},
  setAttribute(k,v) {this.attributes[k]=v;},
  addEventListener() {}, removeEventListener() {},
};}
const refs = {card: node(), badge: node(), unassigned: node(), rows: {}};
for (const phase of ['l1','l2','l3']) {
  refs.rows[phase] = Object.fromEntries('row status reading limit track fill margin batteries'.split(' ').map(k=>[k,node()]));
}
panel._r = {phases: refs};
if (scenario.before) {
  panel._hass.states[id].attributes.monitoring = scenario.before;
  panel._patchPhaseMonitoring();
  panel._hass.states[id].attributes.monitoring = scenario.attrs.monitoring;
}
const model = panel._phaseMonitoringState();
panel._patchPhaseMonitoring();
if (scenario.advance) {
  clock += scenario.advance*1000;
  const pending = [...timers.values()]; timers.clear();
  for (const timer of pending) timer.fn();
}
if (scenario.disconnect) {
  panel._detachDailyOperationGlobalListeners = () => {};
  panel.disconnectedCallback();
}
process.stdout.write(JSON.stringify({model, refs, timerCount: timers.size}));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""


def _phase(**kwargs):
    return dict(sensor="sensor.l1", reading_a=10, limit_a=25, utilization_pct=40,
                headroom_a=15, overload_a=0, status="normal", batteries=["Battery A"], **kwargs)


def _run(phases=None, **scenario):
    attrs = {"monitoring": phases or {}, **scenario.pop("attrs", {})}
    result = subprocess.run(
        [shutil.which("node"), "--experimental-vm-modules", "-e", HARNESS, str(PANEL)],
        input=json.dumps({"attrs": attrs, **scenario}), capture_output=True, encoding="utf-8", timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_monitor_renders_current_limit_headroom_and_battery_assignment():
    result = _run({"l1": _phase()}, attrs={"unassigned_batteries": ["Portable battery"]})
    row = result["refs"]["rows"]["l1"]
    assert result["refs"]["card"]["hidden"] is False
    assert row["reading"]["textContent"] == "10.0 A · Import"
    assert row["reading"]["_moreInfoEntity"] == "sensor.l1"
    assert row["limit"]["textContent"] == "Limit 25.0 A"
    assert row["margin"]["textContent"] == "15.0 A remaining"
    assert row["batteries"]["textContent"] == "Battery A"
    assert row["fill"]["style"]["width"] == "40%"
    assert row["track"]["attributes"]["aria-valuenow"] == 40
    assert result["refs"]["rows"]["l2"]["row"]["hidden"] is True
    assert result["refs"]["unassigned"]["textContent"] == "Unassigned batteries: Portable battery"


@pytest.mark.parametrize("current,direction", [(30,"Import"),(-30,"Export")])
def test_overload_is_visible_in_both_directions_without_overflow(current, direction):
    phase = {**_phase(), "reading_a": current, "utilization_pct": 120,
             "headroom_a": 0, "overload_a": 5, "status": "over_limit"}
    result = _run({"l1": phase})
    row = result["refs"]["rows"]["l1"]
    assert row["row"]["dataset"]["tone"] == "bad"
    assert row["status"]["textContent"] == "Over limit"
    assert row["reading"]["textContent"].endswith(direction)
    assert row["margin"]["textContent"] == "5.0 A over limit"
    assert row["fill"]["style"]["width"] == "100%"
    assert "120%" in row["track"]["attributes"]["aria-valuetext"]


@pytest.mark.parametrize("status", ["disabled", "active"])
def test_monitoring_is_independent_of_protection_switch(status):
    result = _run({"l1": _phase()}, state=status, attrs={"protection_enabled": status=="active"})
    assert result["refs"]["badge"]["textContent"] == ("Protection on" if status=="active" else "Protection off")
    assert result["refs"]["rows"]["l1"]["reading"]["textContent"] == "10.0 A · Import"


@pytest.mark.parametrize("reason,label", [("sensor_stale","Reading is stale"),("sensor_unavailable","Check current sensor")])
def test_lost_reading_clears_the_previous_good_bar_and_margin(reason, label):
    phase = {**_phase(), "reading_a": None, "utilization_pct": None,
             "headroom_a": None, "status": "unavailable", "reason": reason}
    result = _run({"l1": phase}, before={"l1": _phase()})
    row = result["refs"]["rows"]["l1"]
    assert row["reading"]["textContent"] == "—"
    assert row["track"]["hidden"] is True
    assert row["fill"]["style"]["width"] == "0%"
    assert row["margin"]["textContent"] == label


@pytest.mark.parametrize("scenario", [{"age":66},{"state":"unavailable"},{"state":"unknown"}])
def test_unavailable_or_outdated_status_entity_never_keeps_healthy_readings(scenario):
    result = _run({"l1": _phase()}, **scenario)
    row = result["refs"]["rows"]["l1"]
    assert row["reading"]["textContent"] == "—"
    assert row["track"]["hidden"] is True
    assert result["model"]["rows"][0]["headroom"] is None


@pytest.mark.parametrize("scenario", [{},{"missing":True}])
def test_unconfigured_installation_has_no_empty_card(scenario):
    assert _run(**scenario)["refs"]["card"]["hidden"] is True


def test_zero_is_a_valid_reading_and_dutch_labels_are_translated():
    phase = {**_phase(), "reading_a": 0, "utilization_pct": 0, "headroom_a": 25}
    row = _run({"l1":phase}, language="nl")["refs"]["rows"]["l1"]
    assert row["reading"]["textContent"] == "0,0 A · Geen stroom"
    assert row["margin"]["textContent"] == "25,0 A beschikbaar"
    assert row["track"]["hidden"] is False


def test_incomplete_configuration_does_not_claim_safe_capacity():
    phase = {**_phase(), "limit_a": None, "headroom_a": None,
             "utilization_pct": None, "status":"not_configured"}
    row = _run({"l1":phase})["refs"]["rows"]["l1"]
    assert row["status"]["textContent"] == "Complete phase setup"
    assert row["limit"]["textContent"] == "No limit configured"
    assert row["track"]["hidden"] is True


@pytest.mark.parametrize("age,advance", [(0, 66), (64, 2)])
def test_readings_expire_without_any_new_hass_event(age, advance):
    result = _run({"l1": {**_phase(), "age_s": age}}, advance=advance)
    row = result["refs"]["rows"]["l1"]
    assert row["reading"]["textContent"] == "—"
    assert row["track"]["hidden"] is True
    assert row["margin"]["textContent"] == "Reading is stale"
    assert result["timerCount"] == 0


def test_disconnect_cancels_phase_expiration_timer():
    assert _run({"l1": _phase()}, disconnect=True)["timerCount"] == 0
