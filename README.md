# Through the Lines

Trace how the congressional district at an address has changed across redistricting cycles, annotated with who drew each plan (legislature, court, commission, or remedial special master) and whether a court later struck it down.

Most tools show your *current* district. Through the Lines answers the harder question: how has it changed over time, and who was responsible for each change?

**Live:** https://throughthelines.org

> **Status:** v0.6.0, live in production. Current coverage is North Carolina, across the 107th–120th Congresses (2001–2027). The pipeline and schema are built to extend further. Pennsylvania, Texas, and Virginia are planned next.

## How it works

Each address is resolved entirely client side, there is no backend and no data collection of any kind. The Census Geocoder converts addresses into a 2020 Census block, and a prebuilt lookup table maps that block to its district under every Congress in scope. Districts are matched against each decade's own Census block geometry (2000 blocks for the 107th–112th, 2010 for the 113th–117th, 2020 for the 118th–120th) so there's no time-warping of modern boundaries onto past maps. Addresses are never sent anywhere but the [U.S. Census Geocoder](https://geocoding.geo.census.gov/geocoder/).

The plan-origin metadata (who drew each plan, whether it was struck down, and the governing litigation) is hand-curated into per-plan YAML files.

Full detail lives in the in-app docs: https://throughthelines.org/docs

## Architecture

Two decoupled halves:

- **Build pipeline** (`pipeline/`, Python): Fetches upstream sources (district polygons from Lewis or the enacting state authority, Voteview members, Census blocks and equivalency files), validates the plan YAMLs, builds vector tiles plus the block-lookup and metadata JSON, and uploads everything to Cloudflare R2. A `manifest.json`, written last, is the atomic pointer the frontend reads.
- **Frontend** (`apps/web/`, SvelteKit static): A static site on Cloudflare Pages. At runtime it reads `manifest.json` from R2, loads vector tiles via HTTP range requests, and geocodes client-side.

```
through-the-lines/
├── apps/web/          # SvelteKit static frontend (Cloudflare Pages)
├── pipeline/          # Python build pipeline (uv)
├── config/            # project + source configuration (TOML)
├── data/plans/NC/     # hand-curated plan-metadata YAMLs  ← the dataset
├── deploy.sh          # one-shot redeploy
└── .github/workflows/ # CI
```

## Contributing plan metadata (no code required)

The lowest-friction contribution is curating plan-origin metadata.

Each plan is one YAML file under `data/plans/<state>/`. Curation-sensitive fields use a three-valued model: a real value, `unknown` (researched, not determinable), or `pending` (not yet curated). Fill in the fields, set `curation_status`, cite your sources, and open a pull request. CI validates every YAML against the schema on each PR.

See the curation guide: https://throughthelines.org/docs/curation

## Development (code contributors)

### Frontend

Requires `Node 22` and `pnpm 10.33.4`.

```bash
cd apps/web
cp .env.example .env      # dev defaults: serves data/derived at /derived
pnpm install
pnpm dev
```

The map and address lookup read artifacts from `data/derived/`, which the dev server serves locally. Those artifacts come from the pipeline, so the data build below must have run at least once for the lookup to work; the rest of the UI runs without it.

### Build pipeline

Requires `Python 3.11` and [`uv`](https://docs.astral.sh/uv/). The tile and basemap steps also need the [`tippecanoe`](https://www.google.com/search?q=tippacanoe+flt&oq=tippacanoe+flt+&gs_lcrp=EgZjaHJvbWUyBggAEEUYOTIICAEQABgWGB4yBwgCEAAY7wUyCggDEAAYgAQYogQyBwgEEAAY7wUyCggFEAAYogQYiQUyBwgGEAAY7wXSAQgzOTYwajBqN6gCALACAA&sourceid=chrome&ie=UTF-8) and [`pmtiles`](https://github.com/protomaps/pmtiles) command-line tools.

```bash
cd pipeline
uv sync
```

Run the stages in order (the steps after `stitch` are independent of one another):

```bash
uv run pipeline fetch               # download upstream sources
uv run pipeline scaffold-plans      # generate placeholder plan YAMLs
uv run pipeline normalize-geometry  # normalize non-Lewis shapefiles to GeoJSON
uv run pipeline stitch              # join metadata onto Lewis polygons
uv run pipeline members             # slice Voteview into members.json
uv run pipeline blocks              # build the block → district lookup
uv run pipeline tiles               # build PMTiles (needs tippecanoe)
uv run pipeline basemap             # extract the basemap (needs pmtiles)
uv run pipeline plan-index          # build plan_index.json
uv run pipeline manifest            # build manifest.json (run last)
```

`uv run pipeline publish` uploads the built artifacts to R2 and requires credentials in `pipeline/.env`:

```
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ACCOUNT_ID=...
R2_BUCKET=ttl-artifacts
```

## Deploying

`./deploy.sh` (runnable from anywhere in the tree) chains the redeploy loop, it rebuilds the manifest with the current git SHA, publishes to R2, builds the frontend, and deploys to Cloudflare Pages. It does **not** run the heavy data build (it assumes the artifacts under `data/derived/` are already built). It requires `apps/web/.env.production` (the prod `PUBLIC_ARTIFACTS_*` values), an authenticated `wrangler`, and R2 credentials.

## CI

GitHub Actions runs on every push to `main` and every pull request: 

- Python type-checking (`mypy`) and plan-YAML validation 
- Frontend type-checking (`svelte-check`) and linting. 

It does not run the data build.

## License

Code is MIT (`LICENSE`). The plan-metadata dataset under `data/plans/` is CC-BY-SA 4.0 (`LICENSE-DATA`).

## Acknowledgments

Through the Lines is the connective layer over several existing resources: 

- Jeffrey Lewis's congressional district shapefiles 
- State redistricting authorities (e.g. the North Carolina General Assembly)
- Voteview
- The U.S. Census Bureau 
- Protomaps
- Justin Levitt's _All About Redistricting_ 

The full source list and citations are on the [data page](https://throughthelines.org/data).
