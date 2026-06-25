# Through the Lines: Web Frontend

The static SvelteKit frontend for [Through the Lines](https://throughthelines.org). It reads `manifest.json` from Cloudflare R2 at runtime, geocodes addresses client-side, and renders the map, district timeline, and plan detail. There is no backend.

This is one half of the project; the build pipeline lives in [`../../pipeline`](../../pipeline). For the project overview, see the [root README](../../README.md).

## Stack

- [SvelteKit](https://svelte.dev/docs/kit) (static, `adapter-static`) + Svelte 5 (runes)
- TypeScript
- Tailwind CSS v4
- [MapLibre GL](https://maplibre.org/) + [PMTiles](https://github.com/protomaps/pmtiles) for the map
- [mdsvex](https://mdsvex.pngwn.io/) for the docs pages (`.svx`)

## Setup

Requires Node 22 and `pnpm`.

```bash
cp .env.example .env   # dev defaults
pnpm install
pnpm dev
```

The map and address lookup load data artifacts from `../../data/derived`, which a dev-only Vite middleware serves at `/derived`. The [pipeline](../pipeline) must have built those artifacts at least once for the lookup to work; the rest of the UI runs without them.

## Environment

Two build-time public variables control where data artifacts are loaded from:

- `PUBLIC_ARTIFACTS_BASE`: base URL for `manifest.json` and the data artifacts. Dev: `/derived`. Production: the R2 public base.
- `PUBLIC_ARTIFACTS_LAYOUT`: `flat` (dev; artifacts served directly under the base) or `versioned` (production; paths resolved under the manifest's per-build `v/{sha}/` prefix).

Dev values come from `.env`; production values live in `.env.production`, which the deploy requires. Because these are baked in at build time, the production build must run with `.env.production` present.

## Scripts

```bash
pnpm dev        # dev server
pnpm build      # production build → build/
pnpm preview    # preview the production build
pnpm check      # type-check (svelte-check)
pnpm lint       # Prettier check + ESLint
pnpm format     # Prettier write
pnpm gen:map    # regenerate the US-states watermark SVG paths
pnpm gen:nc12   # regenerate the NC-12 hero specimen SVG path
```

The `gen:*` scripts are one-off generators for static SVG path data; run them only when that source data changes.

## Structure

```
src/
├── routes/   # pages: home, /[state], /docs/*, /data, /changelog, /contact
└── lib/      # components and logic — map, timeline, plan detail, geocoder,
              #   and the manifest / plan-index / block-lookup / members loaders
static/       # fonts, map sprites, favicon, robots.txt
scripts/      # build-time SVG path generators (see gen:* above)
```

## Build & deploy

`pnpm build` produces a static site in `build/` (SPA fallback `index.html`). Deployment to Cloudflare Pages is handled by [`../../deploy.sh`](../../deploy.sh), which builds the frontend after publishing the data to R2. See the [root README](../../README.md) for the full deploy flow.
