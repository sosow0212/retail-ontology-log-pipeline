#!/usr/bin/env bash
# Local k3d cluster lifecycle with an isolated kubeconfig.
# Usage: scripts/cluster.sh {up|stop|start|down|status}

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

K3D_CONFIG="${REPO_ROOT}/deploy/k3d/cluster.yaml"
HOST_DATA_DIR="${REPO_ROOT}/data"

cluster_exists() {
  k3d cluster list "${CLUSTER_NAME}" >/dev/null 2>&1
}

write_kubeconfig() {
  mkdir -p "$(dirname "${LOCAL_KUBECONFIG}")"
  local temporary_file="${LOCAL_KUBECONFIG}.tmp"
  (umask 077 && k3d kubeconfig get "${CLUSTER_NAME}" >"${temporary_file}")
  mv "${temporary_file}" "${LOCAL_KUBECONFIG}"
}

wait_for_nodes() {
  kube wait --for=condition=Ready node --all --timeout=180s >/dev/null
}

cmd_up() {
  require_command docker k3d kubectl
  if cluster_exists; then
    log "cluster '${CLUSTER_NAME}' already exists; reusing it"
  else
    mkdir -p "${HOST_DATA_DIR}"
    log "creating k3d cluster '${CLUSTER_NAME}'"
    # The positional name overrides metadata.name so CLUSTER_NAME always matches the context.
    k3d cluster create "${CLUSTER_NAME}" --config "${K3D_CONFIG}" \
      --kubeconfig-update-default=false \
      --kubeconfig-switch-context=false \
      --volume "${HOST_DATA_DIR}:/mnt/host-data@server:0"
  fi
  write_kubeconfig
  require_local_context
  wait_for_nodes
  log "cluster is ready (context ${KUBE_CONTEXT}, kubeconfig ${LOCAL_KUBECONFIG})"
}

cmd_stop() {
  require_command k3d
  cluster_exists || die "cluster '${CLUSTER_NAME}' does not exist"
  log "stopping cluster '${CLUSTER_NAME}' (volumes and data are kept)"
  k3d cluster stop "${CLUSTER_NAME}"
}

cmd_start() {
  require_command docker k3d kubectl
  cluster_exists || die "cluster '${CLUSTER_NAME}' does not exist. Run 'make up' first"
  log "starting cluster '${CLUSTER_NAME}'"
  k3d cluster start "${CLUSTER_NAME}"
  write_kubeconfig
  require_local_context
  wait_for_nodes
  # Jobs started right after a restart fail if the catalog or storage is still coming up.
  if kube get namespace platform >/dev/null 2>&1; then
    log "waiting for platform workloads"
    kube --namespace platform wait --for=condition=Available deployment --all --timeout=300s >/dev/null
    kube --namespace platform wait --for=condition=Ready pod --selector=cnpg.io/cluster --timeout=300s >/dev/null
  fi
  log "cluster '${CLUSTER_NAME}' is running"
}

cmd_down() {
  require_command k3d
  if cluster_exists; then
    log "deleting cluster '${CLUSTER_NAME}' and all of its data"
    k3d cluster delete "${CLUSTER_NAME}"
  else
    log "cluster '${CLUSTER_NAME}' does not exist"
  fi
  rm -f "${LOCAL_KUBECONFIG}"
}

cmd_status() {
  require_command k3d kubectl
  if ! cluster_exists; then
    log "cluster '${CLUSTER_NAME}' does not exist"
    return 0
  fi
  k3d cluster list "${CLUSTER_NAME}"
  if [[ -f "${LOCAL_KUBECONFIG}" ]] && kube get --raw /readyz --request-timeout=5s >/dev/null 2>&1; then
    require_local_context
    kube get nodes
    kube get pods --all-namespaces
  else
    log "cluster API is not reachable (the cluster may be stopped)"
  fi
}

case "${1:-}" in
  up) cmd_up ;;
  stop) cmd_stop ;;
  start) cmd_start ;;
  down) cmd_down ;;
  status) cmd_status ;;
  *) die "usage: $0 {up|stop|start|down|status}" ;;
esac
