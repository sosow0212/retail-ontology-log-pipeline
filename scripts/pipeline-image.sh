#!/usr/bin/env bash
# Builds the data-pipeline image and imports it into the local cluster.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

IMAGE="${PIPELINE_IMAGE:-retail-pipeline:dev}"

require_command docker k3d
log "building ${IMAGE}"
docker build --tag "${IMAGE}" "${REPO_ROOT}/data-pipeline"

if k3d cluster list "${CLUSTER_NAME}" >/dev/null 2>&1; then
  log "importing ${IMAGE} into cluster '${CLUSTER_NAME}'"
  k3d image import "${IMAGE}" --cluster "${CLUSTER_NAME}"
else
  warn "cluster '${CLUSTER_NAME}' does not exist; skipped the image import"
fi
