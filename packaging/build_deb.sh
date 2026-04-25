#!/bin/bash
set -e

REQUIRED_CMDS="dch dpkg-buildpackage"
for cmd in $REQUIRED_CMDS; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: '$cmd' not found. Install build prerequisites:"
        echo "  sudo apt-get install devscripts dpkg-dev debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools"
        exit 1
    fi
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PROJECT_NAME="dmj-vault"
OUTPUT_DIR="/tmp/${PROJECT_NAME}-packages"
MAINTAINER_NAME="${DEBFULLNAME:-Max}"
MAINTAINER_EMAIL="${DEBEMAIL:-max@derkacz-mj.com}"

QUICK_BUILD="${QUICK_BUILD:-0}"

usage() {
    local pkgs
    pkgs=$(ls -1 "$SCRIPT_DIR" | grep -v '\.sh$' | tr '\n' ',' | sed 's/,$//')
    echo "Usage: $0 <package|all> [--jobs N]"
    echo "  package: $pkgs"
    echo ""
    echo "Options:"
    echo "  --jobs N    Max parallel builds for 'all' (default: 4)"
    echo ""
    echo "Environment:"
    echo "  QUICK_BUILD=1  skip packages already built at current version"
    exit 1
}

build_package() {
    local pkg="$1"
    local pkg_debian="$SCRIPT_DIR/$pkg/debian"
    local pkg_pyproject="$SCRIPT_DIR/$pkg/pyproject.toml"

    if [ ! -d "$pkg_debian" ]; then
        echo "Error: packaging directory not found: $pkg_debian"
        return 1
    fi

    echo "=== Building package: $pkg ==="

    local base_version
    base_version="$(cat "$pkg_debian/version.txt")"
    local timestamp
    timestamp="$(date +%s)"
    local full_version="${base_version}b${timestamp}"

    local WORK_DIR
    WORK_DIR="$(mktemp -d /tmp/${PROJECT_NAME}-build-${pkg}-XXXXXX)"
    local BUILD_DIR="$WORK_DIR/src"
    mkdir "$BUILD_DIR"
    echo "Building in $BUILD_DIR (version: $full_version)"

    local src_dir
    src_dir=$(sed -n 's/^source-dir = "\(.*\)"/\1/p' "$pkg_pyproject")
    if [ -n "$src_dir" ]; then
        if [ -d "$PROJECT_DIR/$src_dir" ]; then
            mkdir -p "$BUILD_DIR/$(dirname "$src_dir")"
            cp -r "$PROJECT_DIR/$src_dir" "$BUILD_DIR/$src_dir"
        else
            echo "Error: source-dir '$src_dir' not found for $pkg"
            rm -rf "$WORK_DIR"
            return 1
        fi
    fi

    cp "$pkg_pyproject" "$BUILD_DIR/pyproject.toml"
    cp -r "$pkg_debian" "$BUILD_DIR/debian"

    cd "$BUILD_DIR" || return 1

    DEBEMAIL="$MAINTAINER_EMAIL" DEBFULLNAME="$MAINTAINER_NAME" \
        dch -c debian/changelog --newversion "$full_version" --distribution unstable "Build $full_version"

    dpkg-buildpackage -us -uc -b

    mkdir -p "$OUTPUT_DIR"
    for deb in "$WORK_DIR"/*.deb; do
        if [ -f "$deb" ]; then
            rm -f "${OUTPUT_DIR}/${pkg}_"*.deb
            cp "$deb" "$OUTPUT_DIR/"
        fi
    done

    cd "$PROJECT_DIR"
    rm -rf "$WORK_DIR"
    echo "=== Done: $pkg ==="
}

needs_build() {
    local pkg="$1"
    local base_version
    base_version="$(cat "$SCRIPT_DIR/$pkg/debian/version.txt")"
    if ls "${OUTPUT_DIR}/${pkg}_${base_version}b"*.deb >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

build_all_parallel() {
    local LOG_DIR
    LOG_DIR="$(mktemp -d /tmp/${PROJECT_NAME}-build-logs-XXXXXX)"
    declare -A PIDS LOGS
    local FAILED_PKGS=()
    local HAS_FAILURE=0
    local QUEUE=($VALID_PACKAGES)
    local QUEUE_IDX=0

    while [ "$QUEUE_IDX" -lt "${#QUEUE[@]}" ] && [ "${#PIDS[@]}" -lt "$MAX_JOBS" ]; do
        local pkg="${QUEUE[$QUEUE_IDX]}"
        LOGS[$pkg]="$LOG_DIR/$pkg.log"
        build_package "$pkg" >"${LOGS[$pkg]}" 2>&1 &
        PIDS[$pkg]=$!
        QUEUE_IDX=$((QUEUE_IDX + 1))
    done

    while [ "${#PIDS[@]}" -gt 0 ]; do
        for pkg in "${!PIDS[@]}"; do
            local pid="${PIDS[$pkg]}"
            if ! kill -0 "$pid" 2>/dev/null; then
                if wait "$pid" 2>/dev/null; then
                    echo "BUILT $pkg"
                else
                    echo "FAILED $pkg"
                    FAILED_PKGS+=("$pkg")
                    HAS_FAILURE=1
                fi
                unset "PIDS[$pkg]"
                if [ "$HAS_FAILURE" -eq 1 ]; then
                    for p in "${PIDS[@]}"; do
                        kill "$p" 2>/dev/null || true
                    done
                    wait 2>/dev/null
                    PIDS=()
                    break
                fi
                if [ "$QUEUE_IDX" -lt "${#QUEUE[@]}" ] && [ "${#PIDS[@]}" -lt "$MAX_JOBS" ]; then
                    local next="${QUEUE[$QUEUE_IDX]}"
                    LOGS[$next]="$LOG_DIR/$next.log"
                    build_package "$next" >"${LOGS[$next]}" 2>&1 &
                    PIDS[$next]=$!
                    QUEUE_IDX=$((QUEUE_IDX + 1))
                fi
            fi
        done
        [ "${#PIDS[@]}" -gt 0 ] && sleep 0.5
    done

    mkdir -p "$OUTPUT_DIR"
    : >"$OUTPUT_DIR/latest_build.log"
    for pkg in $(echo "${!LOGS[@]}" | tr ' ' '\n' | sort); do
        [[ " ${FAILED_PKGS[*]} " == *" $pkg "* ]] && continue
        echo "========== $pkg ==========" >>"$OUTPUT_DIR/latest_build.log"
        cat "${LOGS[$pkg]}" >>"$OUTPUT_DIR/latest_build.log"
    done
    for pkg in "${FAILED_PKGS[@]}"; do
        echo "" >>"$OUTPUT_DIR/latest_build.log"
        echo "!!!!!!!!!! FAILED: $pkg !!!!!!!!!!" >>"$OUTPUT_DIR/latest_build.log"
        cat "${LOGS[$pkg]}" >>"$OUTPUT_DIR/latest_build.log"
    done

    rm -rf "$LOG_DIR"

    if [ "$HAS_FAILURE" -eq 1 ]; then
        echo ""
        echo "Build FAILED. See $OUTPUT_DIR/latest_build.log for details."
        exit 1
    fi

    echo ""
    echo "All packages built. Log: $OUTPUT_DIR/latest_build.log"
    echo ""
    echo "Packages in $OUTPUT_DIR:"
    ls -1 "$OUTPUT_DIR"/*.deb 2>/dev/null | while read -r deb; do
        echo "  $deb"
    done
}

TARGET=""
MAX_JOBS=4
while [ $# -gt 0 ]; do
    case "$1" in
        --jobs) MAX_JOBS="$2"; shift 2 ;;
        -*) echo "Unknown option: $1"; usage ;;
        *) TARGET="$1"; shift ;;
    esac
done

[ -z "$TARGET" ] && usage

VALID_PACKAGES=$(ls -1 "$SCRIPT_DIR" | grep -v '\.sh$' | sort)

if [ "$TARGET" = "all" ]; then
    if [ "$QUICK_BUILD" = "1" ]; then
        FILTERED=""
        for pkg in $VALID_PACKAGES; do
            if needs_build "$pkg"; then
                FILTERED="$FILTERED $pkg"
            else
                echo "SKIP $pkg (up-to-date)"
            fi
        done
        VALID_PACKAGES="$(echo $FILTERED)"
        if [ -z "$VALID_PACKAGES" ]; then
            echo "All packages up-to-date, nothing to build."
            exit 0
        fi
    fi
    build_all_parallel
elif [ -d "$SCRIPT_DIR/$TARGET" ]; then
    build_package "$TARGET"
    echo ""
    echo "Done. Package in $OUTPUT_DIR:"
    ls -1 "$OUTPUT_DIR/${TARGET}_"*.deb 2>/dev/null | while read -r deb; do
        echo "  $deb"
    done
else
    echo "Error: unknown package '$TARGET'"
    usage
fi
