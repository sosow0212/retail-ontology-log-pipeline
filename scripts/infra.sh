#!/usr/bin/env bash
# Deploys or removes the platform releases defined in deploy/helmfile.yaml.gotmpl.
# Usage: scripts/infra.sh {up|down}

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

HELMFILE="${REPO_ROOT}/deploy/helmfile.yaml.gotmpl"

run_helmfile() {
  helmfile --file "${HELMFILE}" --kube-context "${KUBE_CONTEXT}" "$@"
}

cmd_up() {
  require_command kubectl helm helmfile
  require_local_context
  log "syncing platform releases"
  run_helmfile sync
  log "platform releases are ready"
}

cmd_down() {
  require_command kubectl helm helmfile
  require_local_context
  log "destroying platform releases"
  run_helmfile destroy
}

case "${1:-}" in
  up) cmd_up ;;
  down) cmd_down ;;
  *) die "usage: $0 {up|down}" ;;
esac
