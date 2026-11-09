# OpenBattery provenance and compatibility

OpenBattery is an independent fork of [ffunes/Omnibattery](https://github.com/ffunes/Omnibattery), originally Marstek Venus Energy Manager. It is maintained separately by [thomasvt1](https://github.com/thomasvt1). It is not an official upstream release.

The original project and its contributors retain their copyright and attribution. The GNU General Public License version 3 in LICENSE is unchanged. Git history and the inherited CHANGELOG.md preserve the original development record.

The fork adds optional monthly full-charge scheduling, forecast-based day selection, an early actual-price trigger, regression coverage, and OpenBattery branding. The default monthly source uses no forecast. The Jeroen.nl adapter is optional; see the provider's usage terms linked from the monthly scheduling documentation.

## Compatibility

The internal Home Assistant domain remains `omnibattery`, as do integration storage keys, existing entity IDs, service names and dashboard URLs. These are compatibility identifiers, not the displayed brand. Do not install OpenBattery and OmniBattery side by side: they use the same component directory and control the same batteries.

The `main` branch inherited from the existing fork is retained. The OpenBattery development and documentation default branch is `openbattery`.

## Assets

The OpenBattery icon and wordmark are new assets generated for this fork. The dashboard screenshot shows the fork's local simulated Home Assistant setup. Older hardware and configuration screenshots in the inherited documentation remain reference material and may display the previous project name.
