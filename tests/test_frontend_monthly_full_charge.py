"""Execute the shipped monthly full-charge card model and DOM patch in Node."""
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
const scenario = JSON.parse(fs.readFileSync(0, 'utf8'));
const clock = Date.parse(scenario.now || '2026-11-24T13:30:00Z');
function node(tag) {
  const n = {
    tag, className: '', style: {props: {}, setProperty(k, v) {this.props[k] = v;}},
    dataset: {}, attributes: {}, textContent: '', hidden: false, title: '', children: [],
    classList: {add() {}, remove() {}},
    setAttribute(k, v) {this.attributes[k] = v;},
    appendChild(child) {
      this.children.push(child);
      Object.defineProperty(child, 'parentNode', {value: this, configurable: true, enumerable: false});
      return child;
    },
    remove() {
      if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(c => c !== this);
    },
    addEventListener() {}, removeEventListener() {},
  };
  return n;
}
const context = vm.createContext({
  HTMLElement: class {},
  customElements: { get() {}, define(name, cls) { Panel = cls; } },
  Date: class extends Date {
    constructor(...args) { if (args.length) super(...args); else super(clock); }
    static now() { return clock; }
  },
  document: { createElement: node },
  Intl,
});
const runtime = new vm.SourceTextModule(fs.readFileSync(process.argv[1], 'utf8'), { context });
await runtime.link(() => { throw new Error('Unexpected external import'); });
await runtime.evaluate();
const panel = Object.create(Panel.prototype);
const id = 'sensor.renamed_full_charge';
panel._panelConfig = {};
panel.isConnected = true;
panel._view = 'resumen';
panel._hass = {
  states: scenario.missing ? {} : {[id]: {state: scenario.state || 'idle', attributes: scenario.attrs}},
  entities: {[id]: {entity_id: id, platform: 'omnibattery', translation_key: 'weekly_full_charge'}},
  devices: {},
  locale: {language: scenario.language || 'en', time_format: '24', time_zone: 'server'},
  config: {time_zone: 'Europe/Amsterdam'},
};
const keys = 'card source status days legend eyebrow headline reason updated refresh note batteries credit'.split(' ');
panel._r = {fullCharge: Object.fromEntries(keys.map(k => [k, node()]))};
const runs = scenario.then ? [scenario.attrs, scenario.then] : [scenario.attrs];
let model;
for (const attrs of runs) {
  if (!scenario.missing) panel._hass.states[id].attributes = attrs;
  model = panel._fullChargeState();
  panel._patchFullCharge();
}
const r = panel._r.fullCharge;
const days = (r.dayEls || []).map(d => ({
  kind: d.li.dataset.kind, empty: d.li.dataset.empty, ratio: Number(d.li.style.props['--fc-r']),
  value: d.value.textContent, name: d.name.textContent, date: d.date.textContent, tag: d.tag.textContent,
  label: d.li.attributes['aria-label'],
}));
const text = Object.fromEntries(keys.map(k => [k, {text: r[k].textContent, hidden: r[k].hidden, cls: r[k].className}]));
process.stdout.write(JSON.stringify({model, text, days, dayNodes: r.days.children.length,
  link: r.headline._moreInfoEntity || null, href: r.credit.href || null}));
})().catch(error => {console.error(error); process.exitCode = 1;});
"""

DAYS = [
    {"date": "2026-11-24", "price": 0.213, "known": True, "eligible": True},
    {"date": "2026-11-25", "price": 0.150, "known": True, "eligible": True},
    {"date": "2026-11-26", "price": 0.133, "known": False, "eligible": True},
    {"date": "2026-11-27", "price": 0.162, "known": False, "eligible": True},
    {"date": "2026-11-28", "price": 0.020, "known": False, "eligible": True},
]


def _attrs(**overrides):
    attrs = {
        "schedule": "monthly", "forecast_source": "jeroen_nl", "selected_date": "2026-11-28",
        "monthly_reason": "forecast_cheapest_day", "window_start": "2026-11-24", "window_end": "2026-11-30",
        "forecast_updated": "2026-11-24T05:12:00+00:00", "forecast_stale": False,
        "forecast_days": DAYS, "price_unit": "EUR/kWh", "charge_hours": 1.5,
        "next_forecast_refresh": "2026-11-24T17:12:00+00:00",
        "monthly_batteries": [{"name": "Venus A", "last_full": "2026-11-02"},
                              {"name": "Venus B", "last_full": "2026-10-30"}],
    }
    attrs.update(overrides)
    return attrs


def _run(attrs=None, **scenario):
    result = subprocess.run(
        [shutil.which("node"), "--experimental-vm-modules", "-e", HARNESS, str(PANEL)],
        input=json.dumps({"attrs": attrs if attrs is not None else _attrs(), **scenario}),
        capture_output=True, encoding="utf-8", timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_planned_day_explains_choice_freshness_and_batteries():
    result = _run()
    text = result["text"]
    assert text["card"]["hidden"] is False
    assert (text["source"]["text"], text["source"]["cls"]) == ("Jeroen.nl", "chip chip-neutral")
    assert (text["status"]["text"], text["status"]["cls"]) == ("Planned", "chip chip-good")
    assert text["eyebrow"]["text"] == "Next full charge"
    assert text["headline"]["text"] == "Saturday, November 28"
    assert result["link"] == "sensor.renamed_full_charge"
    assert text["reason"]["text"] == ("Cheapest 1.5 h that day averages €0.020. "
                                      "€0.113 below the next best day (Thursday).")
    assert text["updated"]["text"] == "Forecast 06:12 · 8 h old"
    assert (text["refresh"]["text"], text["refresh"]["hidden"]) == ("Next refresh 18:12", False)
    assert text["batteries"]["text"] == "Venus A · full Nov 2 · Venus B · not yet this month"
    assert text["credit"]["hidden"] is False and result["href"].startswith("https://jeroen.nl/")
    assert text["note"]["text"] == "Bar: average of the cheapest 1.5 h still ahead"


def test_strip_marks_known_forecast_chosen_and_fallback_days():
    days = _run()["days"]
    assert [d["kind"] for d in days] == ["known", "known", "forecast", "forecast", "chosen", "later", "fallback"]
    assert [d["value"] for d in days] == ["€0.213", "€0.150", "€0.133", "€0.162", "€0.020", "—", "—"]
    assert days[0]["name"] == "Today"
    assert days[4]["label"] == "Sat Nov 28: €0.020, Chosen"
    assert days[6]["tag"] == "Fallback" and days[6]["empty"] == "true"
    # Lower prices draw shorter bars; the most expensive day fills the scale.
    assert days[0]["ratio"] == 1 and days[4]["ratio"] < days[2]["ratio"] < days[1]["ratio"]


def test_days_already_past_and_unused_scores_are_not_presented_as_options():
    attrs = _attrs(window_start="2026-11-23", forecast_days=[
        {"date": "2026-11-23", "price": 0.01, "known": True, "eligible": False}, *DAYS[:4],
        {"date": "2026-11-28", "price": 0.02, "known": False, "eligible": False}],
        selected_date="2026-11-26")
    days = _run(attrs)["days"]
    assert [d["kind"] for d in days] == ["past", "known", "known", "chosen", "forecast", "ignored", "later"]
    assert days[0]["value"] == "—"


@pytest.mark.parametrize("scenario", [
    {"attrs": {"schedule": "weekly"}},
    {"missing": True},
    {"state": "disabled"},
    {"state": "unavailable"},
    {"attrs": _attrs(window_start=None)},
])
def test_card_is_hidden_without_a_monthly_decision(scenario):
    result = _run(scenario.pop("attrs", _attrs()), **scenario)
    assert result["text"]["card"]["hidden"] is True
    assert result["model"] is None


@pytest.mark.parametrize("stale,status,headline", [
    (False, "No forecast yet", "Waiting for a price forecast"),
    (True, "Forecast too old", "Forecast too old to use"),
])
def test_missing_or_stale_forecast_warns_and_names_the_fallback_day(stale, status, headline):
    result = _run(_attrs(monthly_reason="waiting_for_forecast", selected_date=None, forecast_stale=stale,
                         forecast_days=[] if not stale else DAYS))
    text = result["text"]
    assert (text["status"]["text"], text["status"]["cls"]) == (status, "chip chip-warn")
    assert text["headline"]["text"] == headline
    assert "Monday, November 30" in text["reason"]["text"]


def test_simple_schedule_shows_the_date_without_a_forecast_strip():
    result = _run({"schedule": "monthly", "forecast_source": "simple", "selected_date": "2026-11-29",
                   "monthly_reason": "monthly_cadence", "window_start": "2026-11-24", "window_end": "2026-11-30",
                   "monthly_batteries": [{"name": "Venus A", "last_full": None}]})
    text = result["text"]
    assert text["headline"]["text"] == "Sunday, November 29"
    assert text["reason"]["text"] == "Last Sunday of the month."
    assert text["days"]["hidden"] is True and text["legend"]["hidden"] is True
    assert text["updated"]["hidden"] is True and text["credit"]["hidden"] is True
    assert result["days"] == []


def test_before_the_window_names_its_first_day():
    result = _run(_attrs(window_start="2026-11-25", selected_date=None, monthly_reason="waiting", forecast_days=[]))
    assert result["text"]["status"]["text"] == "Waiting for window"
    assert result["text"]["headline"]["text"] == "Wednesday, November 25"


def test_before_the_window_a_leftover_forecast_is_not_shown():
    # Seen in local validation: stored evidence from an earlier forecast
    # rendered as a ranked strip and a "0 min old" forecast before the window.
    result = _run(_attrs(window_start="2026-11-25"))
    text = result["text"]
    assert text["status"]["text"] == "Waiting for window"
    assert all(d["value"] == "—" for d in result["days"])
    assert "chosen" not in [d["kind"] for d in result["days"]]
    assert text["updated"]["hidden"] is True and text["refresh"]["hidden"] is True
    # The window's days stay listed; empty bars and their legend do not.
    assert result["text"]["days"]["hidden"] is False and result["text"]["legend"]["hidden"] is True


def test_completed_month_and_charging_states():
    done = _run(_attrs(monthly_reason="already_full_this_month"), state="complete")["text"]
    assert (done["status"]["text"], done["status"]["cls"]) == ("Done this month", "chip chip-good")
    assert done["headline"]["text"] == "Every battery reached 100%"
    assert done["refresh"]["hidden"] is True
    charging = _run(_attrs(monthly_reason="price_threshold", selected_date="2026-11-24"), state="charging")["text"]
    assert charging["headline"]["text"] == "Charging to 100%"
    assert charging["reason"]["text"] == "Started early: the import price reached your trigger."


def test_sensor_units_and_negative_prices_are_formatted():
    days = [{"date": "2026-11-24", "price": -1.0, "known": True, "eligible": True},
            {"date": "2026-11-25", "price": 21.5, "known": False, "eligible": True}]
    result = _run(_attrs(forecast_source="sensor", price_unit="ct/kWh", forecast_days=days, selected_date="2026-11-24"))
    assert [d["value"] for d in result["days"][:2]] == ["−1.0 ct", "21.5 ct"]
    assert result["days"][0]["ratio"] == 0
    assert result["text"]["credit"]["hidden"] is True
    assert result["text"]["source"]["text"] == "Forecast sensor"


def test_dutch_labels_and_number_format():
    text = _run(language="nl")["text"]
    assert text["status"]["text"] == "Gepland"
    assert text["headline"]["text"] == "zaterdag 28 november"
    assert text["reason"]["text"].startswith("De goedkoopste 1,5 uur die dag kosten gemiddeld €0,020.")


def test_shorter_window_reuses_and_trims_day_rows():
    result = _run(_attrs(), then=_attrs(window_start="2026-11-27"), now="2026-11-27T10:00:00Z")
    assert result["dayNodes"] == 4
    assert [d["kind"] for d in result["days"]] == ["forecast", "chosen", "later", "fallback"]
