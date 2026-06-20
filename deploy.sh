#!/usr/bin/env bash

# Deploy script for Through the Lines. Redeploy loop only, assumes the
# heavy data artifacts under data/derived are already built on disk.
#
# Chains the manual deploy procedure into a single fail-fast run:
#   1. pipeline manifest      re-stamp the build with the current git SHA
#   2. pipeline publish       upload versioned artifacts + manifest to R2
#   3. pnpm build             build the static frontend
#   4. wrangler pages deploy
#
# Requires wrangler auth (CLOUDFLARE_API_TOKEN env var or a prior `wrangler login`).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAGES_PROJECT="through-the-lines"
DEPLOY_BRANCH="main"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- Preflight ---
for tool in git uv pnpm; do
  command -v "$tool" >/dev/null 2>&1 || die "required tool not found on PATH: $tool"
done

[ -f "$REPO_ROOT/apps/web/.env.production" ] || die \
  "apps/web/.env.production is missing — the prod build bakes PUBLIC_ARTIFACTS_BASE and PUBLIC_ARTIFACTS_LAYOUT at build time; without it the build silently falls back to dev values and ships a broken site."

GIT_SHA="$(cd "$REPO_ROOT" && git rev-parse --short HEAD)"

if [ -n "$(cd "$REPO_ROOT" && git status --porcelain)" ]; then
  printf '\n\033[1;33mwarning:\033[0m working tree is dirty; deploying SHA %s but on-disk files may differ.\n' "$GIT_SHA"
fi

log "Deploying $PAGES_PROJECT @ $GIT_SHA"

# --- 1 + 2: data manifest + publish (from pipeline/) ---
log "[1/4] Building manifest (git_sha=$GIT_SHA)"
( cd "$REPO_ROOT/pipeline" && THROUGH_THE_LINES_GIT_SHA="$GIT_SHA" uv run pipeline manifest )

log "[2/4] Publishing artifacts to R2"
( cd "$REPO_ROOT/pipeline" && uv run pipeline publish )

# --- 3 + 4: frontend build + Pages deploy (from apps/web/) ---
log "[3/4] Building frontend"
( cd "$REPO_ROOT/apps/web" && pnpm build )

log "[4/4] Deploying to Cloudflare Pages"
( cd "$REPO_ROOT/apps/web" && pnpm dlx wrangler pages deploy build \
    --project-name="$PAGES_PROJECT" --branch="$DEPLOY_BRANCH" )

log "Done. Deployed $PAGES_PROJECT @ $GIT_SHA"
