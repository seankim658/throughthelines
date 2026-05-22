# Self-hosted MapLibre sprites

MapLibre renders basemap point-icons (townspot dots, highway shields,
POI markers) from a sprite atlas, not from system icons. We bundle the
sprite with the site so we don't depend on a third-party CDN at
runtime, matching the same posture as the self-hosted glyphs in
`../fonts/`.

## Contents

| File                  | Purpose                                              |
| --------------------- | ---------------------------------------------------- |
| `v4/light.json`       | Atlas index for the light flavor at 1x DPI          |
| `v4/light.png`        | Icon atlas image at 1x DPI                          |
| `v4/light@2x.json`    | Atlas index at 2x DPI for HiDPI screens             |
| `v4/light@2x.png`     | Icon atlas image at 2x DPI                          |

The `v4/` directory mirrors the upstream layout. The `v4` segment
corresponds to the major version of the `@protomaps/basemaps` style
package, when that package goes to v5 the sprite URL changes and we
refresh accordingly.

## Source

Downloaded from
[`protomaps/basemaps-assets`](https://github.com/protomaps/basemaps-assets).

**Pinned commit:** `028c18f713baecad011301ff7a69acc39bcc2ae7`
(same SHA as `../fonts/`).

To refresh, re-run the download commands in the project notes against
a new SHA and update both this file and `../fonts/README.md` together.

## Served at

These files are served by Cloudflare Pages at the site root, e.g.
`/sprites/v4/light.png`. The MapLibre `sprite` URL in
`apps/web/src/lib/map/StateMap.svelte` references them relatively as
`/sprites/v4/light`.
