#!/usr/bin/env bash
# Downloads the real dunnhumby dataset with the Kaggle CLI.
# Authentication uses your own Kaggle API token; this script only checks that one is
# configured and never reads or prints it.
# Usage: scripts/data-download.sh <owner/dataset> <output-dir>

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

dataset="${1:?dataset slug is required}"
output_dir="${2:?output directory is required}"
KAGGLE_ENV_FILE="${REPO_ROOT}/.local/kaggle.env"

require_command uvx

# Optional repo-local token file; .local/ is gitignored so the token cannot be committed.
if [[ -f "${KAGGLE_ENV_FILE}" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${KAGGLE_ENV_FILE}"
  set +a
fi

if [[ -z "${KAGGLE_API_TOKEN:-}" && -z "${KAGGLE_KEY:-}" \
  && ! -f "${HOME}/.kaggle/access_token" && ! -f "${HOME}/.kaggle/kaggle.json" ]]; then
  die "no Kaggle API token found. Create one at https://www.kaggle.com/settings/api and save it to ~/.kaggle/access_token (chmod 600)"
fi

mkdir -p "${output_dir}"
log "downloading ${dataset} into ${output_dir}"
uvx --from kaggle kaggle datasets download "${dataset}" --path "${output_dir}" --unzip --force
ls -lh "${output_dir}"
