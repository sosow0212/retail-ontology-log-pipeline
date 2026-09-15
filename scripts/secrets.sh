#!/usr/bin/env bash
# Generates local-only credentials into .local/secrets.env (gitignored) and syncs them
# into Kubernetes Secrets. Secret values are never printed.
# Usage: scripts/secrets.sh sync

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

SECRETS_FILE="${REPO_ROOT}/.local/secrets.env"

random_hex() { openssl rand -hex "$1"; }

ensure_secrets_file() {
  [[ -f "${SECRETS_FILE}" ]] && return 0
  mkdir -p "$(dirname "${SECRETS_FILE}")"
  (
    umask 077
    cat >"${SECRETS_FILE}" <<EOF
S3_ACCESS_KEY_ID=lakehouse-$(random_hex 6)
S3_SECRET_ACCESS_KEY=$(random_hex 24)
LAKEKEEPER_DB_PASSWORD=$(random_hex 24)
LAKEKEEPER_ENCRYPTION_KEY=$(random_hex 32)
EOF
  )
  log "generated ${SECRETS_FILE#"${REPO_ROOT}/"}"
}

ensure_namespace() {
  kube create namespace "$1" --dry-run=client -o yaml | kube apply -f - >/dev/null
}

apply_secret() {
  local namespace="$1" name="$2"
  shift 2
  kube --namespace "${namespace}" create secret generic "${name}" "$@" --dry-run=client -o yaml \
    | kube apply -f - >/dev/null
  log "synced secret ${namespace}/${name}"
}

cmd_sync() {
  require_command kubectl openssl
  require_local_context
  ensure_secrets_file
  # shellcheck source=/dev/null
  source "${SECRETS_FILE}"

  ensure_namespace platform
  ensure_namespace pipeline

  local s3_identities
  s3_identities="$(printf '{"identities":[{"name":"lakehouse-admin","credentials":[{"accessKey":"%s","secretKey":"%s"}],"actions":["Admin","Read","List","Tagging","Write"]}]}' \
    "${S3_ACCESS_KEY_ID}" "${S3_SECRET_ACCESS_KEY}")"

  apply_secret platform seaweedfs-s3-config \
    --from-literal=seaweedfs_s3_config="${s3_identities}"
  apply_secret platform lakekeeper-db \
    --type=kubernetes.io/basic-auth \
    --from-literal=username=lakekeeper \
    --from-literal=password="${LAKEKEEPER_DB_PASSWORD}"
  apply_secret platform lakekeeper-encryption \
    --from-literal=encryptionKey="${LAKEKEEPER_ENCRYPTION_KEY}"
  apply_secret pipeline lakehouse-s3 \
    --from-literal=RETAIL_PIPELINE_S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID}" \
    --from-literal=RETAIL_PIPELINE_S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY}"
}

case "${1:-}" in
  sync) cmd_sync ;;
  *) die "usage: $0 sync" ;;
esac
