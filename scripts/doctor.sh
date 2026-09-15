#!/usr/bin/env bash
# Checks local prerequisites without changing anything.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

MINIMUM_DOCKER_MEMORY_GIB=12
missing_tools=0

check_tool() {
  local name="$1"
  shift
  if command -v "${name}" >/dev/null 2>&1; then
    printf '  %-10s %s\n' "${name}" "$("${name}" "$@" 2>/dev/null | head -n 1)"
  else
    printf '  %-10s \033[1;31mmissing\033[0m\n' "${name}"
    missing_tools=1
  fi
}

echo "Tools"
check_tool docker version --format '{{.Client.Version}}'
check_tool k3d version
check_tool kubectl version --client
check_tool helm version --short
check_tool helmfile --version
check_tool uv --version

echo "Docker"
if docker info >/dev/null 2>&1; then
  memory_bytes="$(docker info --format '{{.MemTotal}}')"
  memory_gib=$((memory_bytes / 1024 / 1024 / 1024))
  printf '  memory     %s GiB allocated, %s CPUs\n' "${memory_gib}" "$(docker info --format '{{.NCPU}}')"
  if ((memory_gib < MINIMUM_DOCKER_MEMORY_GIB)); then
    warn "Docker has less than ${MINIMUM_DOCKER_MEMORY_GIB} GiB of memory; later sprints need more"
  fi
else
  printf '  daemon     \033[1;31mnot running\033[0m\n'
  missing_tools=1
fi

echo "Kubernetes contexts"
host_context="$(KUBECONFIG="${HOST_KUBECONFIG}" kubectl config current-context 2>/dev/null || echo '(none)')"
printf '  host       %s (your shell default; never used or modified by this repo)\n' "${host_context}"
printf '  local      %s via %s\n' "${KUBE_CONTEXT}" "${LOCAL_KUBECONFIG#"${REPO_ROOT}/"}"

if ((missing_tools)); then
  die "some prerequisites are missing"
fi
log "all prerequisites are available"
