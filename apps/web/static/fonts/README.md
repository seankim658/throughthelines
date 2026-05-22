# Self-hosted MapLibre glyphs

MapLibre renders all map text (district numbers, basemap labels) from
SDF-encoded glyph PBFs, not from system fonts. We bundle the glyphs
with the site so we don't depend on a third-party CDN at runtime.

## Contents

| File                                | Purpose                                       |
| ----------------------------------- | --------------------------------------------- |
| `Noto Sans Regular/0-255.pbf`       | Basic Latin range. Covers our district labels |
| `Noto Sans Medium/0-255.pbf`        | Basic Latin range. Used by basemap labels     |
| `Noto Sans Italic/0-255.pbf`        | Basic Latin range. Used by basemap labels     |
| `OFL.txt`                           | SIL Open Font License (required attribution)  |

Currently only the `0-255` (Basic Latin) range is bundled for each fontstack used. 
Additional ranges or fontstacks may need to be added if browsing surfaces glyph
warnings in the console. Add files by re-running the download command with the
missing `{fontstack}/{range}.pbf` paths.

## Source

Downloaded from
[`protomaps/basemaps-assets`](https://github.com/protomaps/basemaps-assets).

**Pinned commit:** `028c18f713baecad011301ff7a69acc39bcc2ae7`

To refresh, see the download commands referenced in the project notes
and update this pinned commit.

## Served at

These files are served by Cloudflare Pages at the site root, e.g.
`/fonts/Noto Sans Regular/0-255.pbf`. The MapLibre `glyphs` URL in
`apps/web/src/lib/map/StateMap.svelte` references them relatively.
