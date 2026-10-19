#!/usr/bin/env bash
# Build the A5 pocket edition: interior first, then the cover.
#
# The cover reads the interior's page count to compute the spine, so the order
# matters.  Outputs land in out/book/; the A4 sheets are not touched.
#
#   ./render.sh                  interior + cover
#   ./render.sh --interior-only  interior only
#   ./render.sh --cover-only     cover only, from the existing interior
#
# Options passed to the builders:
#   --base PT      interior base type size (default 10)
#   --pages N      cover: interior page count (default: read from the PDF)
#   --caliper MM   cover: paper caliper in mm per sheet (default 0.11, 90 gsm)
#   --spine MM     cover: final spine width in mm (overrides --caliper)
set -euo pipefail
cd "$(dirname "$0")"

usage() {
    cat <<'EOF'
Build the A5 pocket edition (interior + cover) into out/book/.

  render.sh                  interior + cover
  render.sh --interior-only  interior only
  render.sh --cover-only     cover only, from the existing interior

Options passed to the builders:
  --base PT      interior base type size (default 10)
  --pages N      cover: interior page count (default: read from the PDF)
  --caliper MM   cover: paper caliper in mm per sheet (default 0.11, 90 gsm)
  --spine MM     cover: final spine width in mm (overrides --caliper)
  -h, --help     show this message
EOF
}

interior=1
cover=1
pocket_args=()
cover_args=()

while (($#)); do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --interior-only)
            cover=0
            shift
            ;;
        --cover-only)
            interior=0
            shift
            ;;
        --base)
            pocket_args+=("$1" "${2:?render: $1 needs a value}")
            shift 2
            ;;
        --base=*)
            pocket_args+=("$1")
            shift
            ;;
        --pages|--caliper|--spine)
            cover_args+=("$1" "${2:?render: $1 needs a value}")
            shift 2
            ;;
        --pages=*|--caliper=*|--spine=*)
            cover_args+=("$1")
            shift
            ;;
        *)
            echo "render: unknown option: $1" >&2
            echo >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ((interior)); then
    echo "==> interior"
    python3 book/make_pocket.py ${pocket_args[@]+"${pocket_args[@]}"}
fi

if ((cover)); then
    echo "==> cover"
    python3 book/make_cover.py ${cover_args[@]+"${cover_args[@]}"}
fi
