#!/usr/bin/env bash
# Step functions are called through run_step, which shellcheck cannot follow.
# shellcheck disable=SC2329
#
# Run every check on the whole repository, or on chosen packages. Run with --help
# for usage.
set -uo pipefail

# ---- settings ---------------------------------------------------------------
# Name used for the log folder and messages.
readonly PROJECT="through-the-lines"
# Each package is a folder holding one of these manifests. The package's name is
# its folder's name.
readonly MANIFEST_GLOB="pipeline/pyproject.toml apps/*/package.json"
# Lines of a failed step's log shown in the terminal.
readonly TAIL_LINES=60
# -----------------------------------------------------------------------------

usage() {
    cat <<'EOF'
usage: bash scripts/check.sh [--packages a,b] [--help]

Run every check on the whole repository, or with --packages on chosen packages,
and print one line per step with the time it took.

The pipeline package gets ruff lint, ruff format, mypy, deptry and pytest. The
pytest suite also validates every plan YAML under data/plans. The web package
gets prettier, eslint and svelte-check.

Every step runs even after one fails. A failed step prints the last lines of its
output, and every step's full output stays in the log folder named at the end.
Dependencies are installed in locked mode (uv --locked, pnpm --frozen-lockfile),
so a check never rewrites a lock file, and a lock file that is out of date with
its manifest fails the check. The script exits 1 if any step failed and 2 on a
usage error. A local pass is never release evidence.

The web checks need PUBLIC_ARTIFACTS_BASE and PUBLIC_ARTIFACTS_LAYOUT. When they
are not set, the script uses the dev defaults from apps/web/.env.example. The
values only have to exist, since no check fetches artifacts.

options
  --packages a,b    check only these packages, each named by its folder
                    (pipeline, web). Packages are independent, so a scoped run
                    skips nothing the named packages depend on, but it is never
                    a full check.
  -h, --help        show this help and exit
EOF
}

usage_error() {
    echo "check.sh: $1 Run bash scripts/check.sh --help for usage." >&2
    exit 2
}

scoped=0
packages_option=""
while (($# > 0)); do
    case "$1" in
    -h | --help)
        usage
        exit 0
        ;;
    --packages | --packages=*)
        ((scoped == 0)) || usage_error "--packages is given twice."
        scoped=1
        if [[ "$1" == --packages=* ]]; then
            packages_option="${1#--packages=}"
        else
            (($# > 1)) || usage_error "--packages needs a comma-separated list of packages."
            packages_option="$2"
            shift
        fi
        ;;
    *)
        usage_error "unknown option $1."
        ;;
    esac
    shift
done

cd "$(dirname "$0")/.." || exit 1

# ---- discovery --------------------------------------------------------------
# workspace_folders holds each package's path at the same index as its name.
workspace_packages=()
workspace_folders=()
for manifest in $MANIFEST_GLOB; do
    [[ -f "$manifest" ]] || continue
    folder="${manifest%/*}"
    workspace_packages+=("${folder##*/}")
    workspace_folders+=("$folder")
done

contains() {
    local wanted="$1" candidate
    shift
    for candidate in "$@"; do
        [[ "$candidate" == "$wanted" ]] && return 0
    done
    return 1
}

# join_comma A B... prints its arguments separated by a comma and a space.
join_comma() {
    local IFS=","
    local text="$*"
    echo "${text//,/, }"
}

refuse_packages() {
    usage_error "$1 Packages: $(join_comma ${workspace_packages[@]+"${workspace_packages[@]}"})."
}

# choose_packages reads --packages into chosen, in the order given, with repeats
# dropped. It refuses an empty list, an empty name and an unknown name.
choose_packages() {
    local name names
    chosen=()
    [[ -n "$packages_option" ]] || refuse_packages "--packages needs at least one package."
    IFS="," read -r -a names <<<"$packages_option"
    for name in ${names[@]+"${names[@]}"}; do
        [[ -n "$name" ]] || refuse_packages "--packages $packages_option holds an empty name."
        contains "$name" ${workspace_packages[@]+"${workspace_packages[@]}"} ||
            refuse_packages "$name is not a package."
        contains "$name" ${chosen[@]+"${chosen[@]}"} || chosen+=("$name")
    done
    ((${#chosen[@]} > 0)) || refuse_packages "--packages needs at least one package."
}

chosen=()
skipped=()
if ((scoped == 1)); then
    choose_packages
    for name in ${workspace_packages[@]+"${workspace_packages[@]}"}; do
        contains "$name" "${chosen[@]}" || skipped+=("$name")
    done
else
    chosen=(${workspace_packages[@]+"${workspace_packages[@]}"})
fi

# ---- step runner ------------------------------------------------------------
# bash's time keyword reports elapsed seconds to two decimals, even in bash 3.2.
TIMEFORMAT='%2R'
# macOS sets TMPDIR with a trailing slash, so drop it before adding the name.
temp_root="${TMPDIR:-/tmp}"
log_dir="$(mktemp -d "${temp_root%/}/$PROJECT-check.XXXXXX")"
failed=()

# A scoped run marks every step line, so its output can never pass for a full run.
narrowed_note=""
if ((scoped == 1)); then
    narrowed_note="[packages: $(join_comma "${chosen[@]}")]"
fi

# run_step NAME NOTE COMMAND... runs COMMAND, logging its output to NAME.log and its
# elapsed time to NAME.time. A NOTE that is not empty ends the step's line.
run_step() {
    local name="$1"
    local note="$2"
    shift 2
    local log="$log_dir/$name.log"
    local timing="$log_dir/$name.time"
    local status elapsed
    { time "$@" >"$log" 2>&1; } 2>"$timing"
    status=$?
    elapsed="$(<"$timing")"
    if ((status == 0)); then
        echo "PASS  $name  $elapsed s${note:+  $note}"
        return 0
    fi
    echo "FAIL  $name  $elapsed s${note:+  $note}"
    tail -n "$TAIL_LINES" "$log" | sed 's/^/      /'
    failed+=("$name")
    return 1
}

# ---- pipeline steps ---------------------------------------------------------
# Each runs inside pipeline/, where pyproject.toml holds the tool config.
in_pipeline() { (cd pipeline && "$@"); }

py_lint() { in_pipeline uv run --locked ruff check --output-format concise src tests; }
py_format() { in_pipeline uv run --locked ruff format --check src tests; }
py_types() { in_pipeline uv run --locked mypy; }
py_deps() { in_pipeline uv run --locked deptry src; }
py_tests() { in_pipeline uv run --locked pytest -q -rs; }

# Print each reason tests skipped for, with its count, most first, so a missing
# input never hides inside a passing run. This reads pytest's -rs lines
# ("SKIPPED [3] path: reason").
skip_reasons() {
    awk 'match($0, /^SKIPPED \[[0-9]+\] [^ ]+: /) {
        count[substr($0, RLENGTH + 1)] += substr($0, 10) + 0
    }
    END { for (reason in count) printf "%d\t%s\n", count[reason], reason }' "$1" |
        sort -t "$(printf '\t')" -k1,1nr -k2 |
        awk -F '\t' '{ printf "      %d skipped: %s\n", $1, $2 }'
}

run_pipeline_steps() {
    run_step py-lint "$narrowed_note" py_lint
    run_step py-format "$narrowed_note" py_format
    run_step py-types "$narrowed_note" py_types
    run_step py-deps "$narrowed_note" py_deps
    if run_step py-tests "$narrowed_note" py_tests; then
        tail -n 1 "$log_dir/py-tests.log" | sed 's/^/      /'
        skip_reasons "$log_dir/py-tests.log"
    fi
}

# ---- web steps --------------------------------------------------------------
# Each runs inside apps/web/. The dev defaults stand in for any unset values.
in_web() {
    (
        cd apps/web &&
            export PUBLIC_ARTIFACTS_BASE="${PUBLIC_ARTIFACTS_BASE:-/derived}" &&
            export PUBLIC_ARTIFACTS_LAYOUT="${PUBLIC_ARTIFACTS_LAYOUT:-flat}" &&
            "$@"
    )
}

web_install() { in_web pnpm install --frozen-lockfile; }
web_format() { in_web pnpm exec prettier --check .; }
web_lint() { in_web pnpm exec eslint .; }
web_types() { in_web pnpm run check; }

run_web_steps() {
    if ! run_step web-install "$narrowed_note" web_install; then
        echo "SKIP  web-format, web-lint, web-types  dependencies did not install"
        return
    fi
    run_step web-format "$narrowed_note" web_format
    run_step web-lint "$narrowed_note" web_lint
    run_step web-types "$narrowed_note" web_types
}

run_steps() {
    if contains pipeline "${chosen[@]}"; then
        run_pipeline_steps
    fi
    if contains web "${chosen[@]}"; then
        run_web_steps
    fi
}

# ---- summary ----------------------------------------------------------------
# time reports on the group's standard error, which goes to total.time. The steps'
# own standard error is passed through on fd 3, so nothing they print is lost.
total_time="$log_dir/total.time"
{ time run_steps 2>&3; } 3>&2 2>"$total_time"

echo
echo "Total  $(<"$total_time") s"
echo "Logs: $log_dir"
status=0
if ((${#failed[@]} > 0)); then
    echo "Failed: ${failed[*]}"
    status=1
elif ((scoped == 1)); then
    echo "All checks in this scoped run passed"
else
    echo "All checks passed"
fi
if ((scoped == 1)); then
    echo "SCOPED RUN, not a full check"
    echo "  Covered: $(join_comma "${chosen[@]}")"
    if ((${#skipped[@]} > 0)); then
        echo "  Skipped: $(join_comma "${skipped[@]}")"
    else
        echo "  Skipped: none"
    fi
fi
exit "$status"
