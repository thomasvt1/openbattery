# OpenBattery frontend

`panel.js` is the independently maintained dashboard registered by
`openbattery_brand.py`. It initially preserves the existing layout and behavior;
the visual redesign requires a separately approved concept.

The original `../marstek-panel.js` is kept at the upstream version as a reference
and merge target. It is not loaded by OpenBattery. Do not put fork UI changes there.

All images this panel needs are in `assets/`, resolved relative to the module URL.
There is no build step: HACS installs this directory with the custom integration.

After a design direction is chosen, extract its design tokens, reusable controls,
charts, HA data adapter and screens here in behavior-tested increments. Do not
duplicate battery scheduling or safety algorithms in the frontend.
