# Contributing to Through the Lines

There are two kinds of contributions, and both go through the same pull-request and CI path:

- **Curation (no code):** Researching a plan and filling in its metadata (who drew it, whether a court struck it down, the citations and dates). This is the bulk of the open work and needs no Python or TypeScript.
- **Code:** The build pipeline (`pipeline/`) and the web app (`apps/web/`).

## Curating a plan

Curation is editing one YAML file under `data/plans/<STATE>/`. The full process, the evidentiary bar, and the recording conventions are in the **[Curation guide](https://throughthelines.org/docs/curation)** and the field-by-field schema is in **[Data model & schema](https://throughthelines.org/docs/data-model)**. In short:

1. Pick a plan file, e.g. `data/plans/NC/NC_113_2013.yaml`.
2. Replace each `pending` with a researched value, or with `unknown` if you looked and it cannot be settled.
3. Record every source in `sources`, and every court opinion in `court_citations`.
4. Note where each value came from in short, source-tagged YAML comments. These are for curators and never reach the site.
5. Set `curation_status` and `curation_last_reviewed`.
6. Open a pull request with only your YAML change.

You don't need to run anything locally, the CI validates every plan file on each pull request. To check it yourself first, see [Validating locally](#validating-locally).

If you have a correction but can't open a pull request, open an issue using the **plan metadata correction** template with the plan, the field, the correct value, and your source.

## Contributing code

Setup for a local checkout is in the [README](https://github.com/seankim658/throughthelines). The pipeline (`pipeline/`) uses `uv` and the web app (`apps/web/`) uses `pnpm`.

## Validating locally

From a checkout, `uv run pipeline plan-index` rebuilds the plan index and, in doing so, validates every plan file.

## Conventions

Project-wide conventions such as date semantics, how to record split court votes, source precedence, and the YAML comment style live in the [Curation guide](https://throughthelines.org/docs/curation#recording-conventions) and [Data model & schema](https://throughthelines.org/docs/data-model) docs.
