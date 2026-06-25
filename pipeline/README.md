# Through the Lines: Build Pipeline

Python pipeline that builds the data artifacts behind [Through the Lines](https://throughthelines.org). It fetches upstream sources, validates the plan-metadata YAMLs, builds the vector tiles plus the block-lookup and metadata indexes, and publishes everything to Cloudflare R2.

This is one half of the project; the static frontend lives in [`../apps/web`](../apps/web). For the project overview, see the [root README](../README.md).

## Requirements

- Python 3.11 and [uv](https://docs.astral.sh/uv/)
- [`tippecanoe`](https://github.com/felt/tippecanoe) — for the `tiles` step
- [`pmtiles`](https://github.com/protomaps/pmtiles) — for the `basemap` step

```bash
uv sync
```

## Configuration

Configuration lives in the repo-root [`config/`](../config) directory:

- `sources.toml`: what to fetch and from where (upstream URLs, pinned commits/checksums, per-state sources)
- `project.toml`: project identity, output paths, and coverage scope (states and Congress range)
- `request.toml`: HTTP fetch behavior (timeouts, retries, backoff)

Publishing additionally needs R2 credentials in `pipeline/.env`:

```
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ACCOUNT_ID=...
R2_BUCKET=ttl-artifacts
```

## Running the build

Each stage is a subcommand of `pipeline`. Run them in order:

```bash
uv run pipeline fetch              # download upstream sources
uv run pipeline scaffold-plans     # generate placeholder plan YAMLs
uv run pipeline normalize-geometry # normalize non-Lewis shapefiles to GeoJSON
uv run pipeline stitch             # join plan metadata onto district polygons
uv run pipeline members            # slice Voteview into members.json
uv run pipeline blocks             # build the block → district lookup
uv run pipeline tiles              # build PMTiles (needs tippecanoe)
uv run pipeline basemap            # extract the basemap (needs pmtiles)
uv run pipeline plan-index         # build plan_index.json
uv run pipeline manifest           # build manifest.json (run last)
uv run pipeline publish            # upload artifacts + manifest to R2
```

The stages between `stitch` and `manifest` (`members`, `blocks`, `tiles`, `basemap`, `plan-index`) are independent and can run in any order. `manifest` must run last, it is the atomic pointer the frontend read, and `publish` runs after it.

Most stages accept `--state` (repeatable) to scope the build to specific states. Run `uv run pipeline <command> --help` for per-command flags.

To redeploy without rebuilding the data artifacts, use [`../deploy.sh`](../deploy.sh), which chains `manifest → publish` and the frontend deploy.

## Layout

```
src/pipeline/
├── cli/        # argparse entry points (one module per subcommand)
├── config/     # TOML config loaders and models
├── plans/      # plan-metadata schema, validation, stitch, plan-index
├── blocks/     # block → district lookup build
├── tiles/      # vector-tile generation
├── members/    # Voteview slice
├── geometry/   # non-Lewis shapefile normalization
├── basemap/    # basemap extraction
├── manifest/   # manifest assembly
├── core/       # shared paths, state codes, atomic IO
├── fetch.py    # upstream fetch
└── publish.py  # R2 upload
```

## Type checking

```bash
uv run mypy src
```
