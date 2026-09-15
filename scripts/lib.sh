#!/usr/bin/env bash
# Shared helpers for the local-cluster scripts.
#
# All Kubernetes access goes through the repo-local kubeconfig and an explicit context.
# The host kubeconfig is only read to report its current context and is never passed to
# kubectl, helm, helmfile, or k3d.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-retail-ontology}"
KUBE_CONTEXT="k3d-${CLUSTER_NAME}"
LOCAL_KUBECONFIG="${REPO_ROOT}/.kube/${CLUSTER_NAME}.yaml"

if [[ -z "${HOST_KUBECONFIG:-}" ]]; then
  if [[ -n "${KUBECONFIG:-}" && "${KUBECONFIG}" != "${LOCAL_KUBECONFIG}" ]]; then
    HOST_KUBECONFIG="${KUBECONFIG}"
  else
    HOST_KUBECONFIG="${HOME}/.kube/config"
  fi
fi
export HOST_KUBECONFIG KUBE_CONTEXT
export KUBECONFIG="${LOCAL_KUBECONFIG}"

# Keep Helm repositories and caches inside the repo so the host Helm setup stays untouched.
export HELM_CONFIG_HOME="${REPO_ROOT}/.local/helm/config"
export HELM_CACHE_HOME="${REPO_ROOT}/.local/helm/cache"
export HELM_DATA_HOME="${REPO_ROOT}/.local/helm/data"

log() { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die() {
  printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2
  exit 1
}

require_command() {
  local name
  for name in "$@"; do
    command -v "${name}" >/dev/null 2>&1 \
      || die "'${name}' is not installed. See docs/guides/local-environment.md"
  done
}

# Aborts unless the local kubeconfig targets only the local k3d API server.
require_local_context() {
  [[ -f "${LOCAL_KUBECONFIG}" ]] || die "local kubeconfig not found. Run 'make cluster-up' first"

  local contexts current server
  contexts="$(kubectl config get-contexts -o name)"
  [[ "${contexts}" == "${KUBE_CONTEXT}" ]] \
    || die "refusing to continue: ${LOCAL_KUBECONFIG} must contain only '${KUBE_CONTEXT}'"

  current="$(kubectl config current-context)"
  [[ "${current}" == "${KUBE_CONTEXT}" ]] \
    || die "refusing to continue: current context is '${current}', expected '${KUBE_CONTEXT}'"

  server="$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')"
  [[ "${server}" =~ ^https://(127\.0\.0\.1|0\.0\.0\.0|localhost):[0-9]+$ ]] \
    || die "refusing to continue: API server '${server}' is not a local address"
}

kube() { kubectl --context "${KUBE_CONTEXT}" "$@"; }
