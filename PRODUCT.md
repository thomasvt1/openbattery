# OpenBattery

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Home Assistant custom integration in Python; a custom-element dashboard served as static JavaScript. The current frontend has no build step. The integration domain remains `omnibattery` for compatibility.

## Users

Home Assistant owners monitoring and configuring supported household batteries. The current owner wants system status to be the first thing the dashboard explains, while also retaining power flows, health, phase limits, controller reasoning, upcoming plans, costs and savings.

## Product Purpose

Control compatible home batteries locally where supported, using grid measurements, battery limits, configured schedules and optional price/solar forecasts. Make the current system state understandable and its controls accessible.

## Operating Context

The dashboard runs inside Home Assistant on desktop and mobile. Devices and source entities can be unavailable or stale. Users can have multiple batteries and phases. Existing entity IDs, storage, settings and the `/omnibattery` URL must remain compatible.

## Capabilities and Constraints

- Existing battery controls and safety decisions remain in Python; a frontend redesign must preserve their behavior.
- Weekly/monthly full charges, optional forecast-based monthly selection, dynamic-price controls and phase monitoring are implemented.
- Phase monitoring lists managed batteries. It does not individually manage arbitrary EVs or solar inverters.
- New OpenBattery UI work is separated from the upstream panel so OmniBattery updates can still be merged.
- The user requires design concepts before implementation of a redesign. No visual direction has been selected yet.
- Missing telemetry, uncertainty and protection-off states must remain explicit.

## Brand Commitments

OpenBattery name and the existing fork's battery icon/wordmark. Preserve upstream credit and GPL licensing. The user approved preserving compatibility with OmniBattery installations.

## Evidence on Hand

Runnable isolated HA with a simulated battery and phase meters; dashboard and phase-monitoring captures under `assets/` and `site-docs/assets/`. The local simulator contains illustrative data, not production performance or savings evidence.

## Product Principles

- Explain system status first, with detail available when needed.
- Keep live measurements, forecasts and configured limits distinguishable.
- Preserve safe control behavior and compatibility while improving presentation.
- Keep upstream maintenance practical through explicit ownership and small integration changes.
