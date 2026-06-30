#!/usr/bin/env bash
# sync-vault-mirror.sh - Refresh the private methodology mirror from this repo.
#
# The vault keeps a read-only mirror of the human-readable methodology markdown
# (the dirs below) so the genealogy research loops can link to prompts and review
# cards from Obsidian. Code, CI, specs, fixtures, and project meta stay here only.
# This script makes the vault mirror exactly match the methodology dirs at HEAD.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_VAULT_NAME="$(printf '%s%s %s' Pru sak Vault)"
VAULT_MIRROR="${VAULT_MIRROR:-$HOME/Vaults/$DEFAULT_VAULT_NAME/Genealogy/_Toolkit/autoresearch-genealogy}"

if [ ! -d "$VAULT_MIRROR" ]; then
  echo "[sync-vault-mirror] target not found: $VAULT_MIRROR" >&2
  exit 1
fi

DIRS=(prompts review-cards guides workflows reference checklists walkthroughs)

for d in "${DIRS[@]}"; do
  if [ -d "$REPO/$d" ]; then
    mkdir -p "$VAULT_MIRROR/$d"
    rsync -a --delete "$REPO/$d/" "$VAULT_MIRROR/$d/"
    echo "[sync-vault-mirror] synced $d/"
  fi
done

rsync -a "$REPO/START_HERE.md" "$VAULT_MIRROR/START_HERE.md"
echo "[sync-vault-mirror] synced START_HERE.md"
echo "[sync-vault-mirror] mirror updated to repo HEAD $(git -C "$REPO" rev-parse --short HEAD)"
