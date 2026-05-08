#!/bin/bash
set -e

PROJECT_NAME="dmj-vault"
LOCAL_PKG_DIR="/tmp/${PROJECT_NAME}-packages"
REMOTE_PKG_DIR="/tmp/${PROJECT_NAME}-packages"

usage() {
    echo "Usage: $0 <remote_host>"
    echo ""
    echo "  remote_host   SSH host (from ~/.ssh/config)"
    echo ""
    echo "Example: $0 prod-server"
    exit 1
}

[ $# -lt 1 ] && usage

TARGET="$1"

if [ ! -d "$LOCAL_PKG_DIR" ]; then
    echo "Error: local package directory not found: $LOCAL_PKG_DIR"
    echo "Build packages first: ./build_deb.sh all"
    exit 1
fi

if ! ls "$LOCAL_PKG_DIR/${PROJECT_NAME}-"*.deb >/dev/null 2>&1; then
    echo "Error: no ${PROJECT_NAME}-*.deb files found in $LOCAL_PKG_DIR"
    exit 1
fi

ssh "$TARGET" "command -v rsync >/dev/null || sudo apt install -y rsync"

echo "=== Syncing $LOCAL_PKG_DIR/ → $TARGET:$REMOTE_PKG_DIR/ ==="
rsync -av --delete "$LOCAL_PKG_DIR/" "$TARGET:$REMOTE_PKG_DIR/"

echo ""
echo "=== Installing packages on $TARGET ==="
ssh -t "$TARGET" "apt install -y $REMOTE_PKG_DIR/${PROJECT_NAME}-*.deb"

echo ""
echo "=== Deploy complete ==="
