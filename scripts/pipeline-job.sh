#!/usr/bin/env bash
# Runs a one-off data-pipeline Job in the local cluster, follows its logs, and exits with
# the Job result.
# Usage: scripts/pipeline-job.sh <job-prefix> -- <retail-pipeline arguments...>

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

NAMESPACE="pipeline"
IMAGE="${PIPELINE_IMAGE:-retail-pipeline:dev}"
START_TIMEOUT_SECONDS="${START_TIMEOUT_SECONDS:-180}"
JOB_TIMEOUT_SECONDS="${JOB_TIMEOUT_SECONDS:-3600}"

[[ $# -ge 1 ]] || die "usage: $0 <job-prefix> -- <retail-pipeline arguments...>"
job_prefix="$1"
shift
[[ "${1:-}" == "--" ]] && shift
[[ $# -ge 1 ]] || die "no retail-pipeline arguments were given"

require_command kubectl python3
require_local_context

job_name="${job_prefix}-$(date +%Y%m%d%H%M%S)"
container_args="$(python3 -c 'import json, sys; print(json.dumps(sys.argv[1:]))' "$@")"

kube apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job_name}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: retail-pipeline
    app.kubernetes.io/component: ${job_prefix}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 86400
  template:
    metadata:
      labels:
        app.kubernetes.io/name: retail-pipeline
        app.kubernetes.io/component: ${job_prefix}
    spec:
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
      containers:
        - name: retail-pipeline
          image: ${IMAGE}
          imagePullPolicy: Never
          args: ${container_args}
          envFrom:
            - configMapRef:
                name: retail-pipeline-config
            - secretRef:
                name: lakehouse-s3
          resources:
            requests:
              cpu: 250m
              memory: 1Gi
            limits:
              memory: 3Gi
          volumeMounts:
            - name: host-data
              mountPath: /mnt/host-data
              readOnly: true
      volumes:
        - name: host-data
          hostPath:
            path: /mnt/host-data
            type: Directory
EOF

pod_field() {
  kube --namespace "${NAMESPACE}" get pods --selector "job-name=${job_name}" \
    -o jsonpath="{.items[0]${1}}" 2>/dev/null || true
}

log "waiting for job/${job_name} to start"
deadline=$((SECONDS + START_TIMEOUT_SECONDS))
while ((SECONDS < deadline)); do
  phase="$(pod_field '.status.phase')"
  [[ "${phase}" =~ ^(Running|Succeeded|Failed)$ ]] && break
  waiting_reason="$(pod_field '.status.containerStatuses[0].state.waiting.reason')"
  if [[ "${waiting_reason}" =~ ^(ErrImageNeverPull|ErrImagePull|ImagePullBackOff|CreateContainerConfigError|InvalidImageName)$ ]]; then
    die "pod for job/${job_name} cannot start: ${waiting_reason}"
  fi
  sleep 2
done

kube --namespace "${NAMESPACE}" logs --follow "job/${job_name}" || true

deadline=$((SECONDS + JOB_TIMEOUT_SECONDS))
while ((SECONDS < deadline)); do
  succeeded="$(kube --namespace "${NAMESPACE}" get job "${job_name}" -o jsonpath='{.status.succeeded}')"
  failed="$(kube --namespace "${NAMESPACE}" get job "${job_name}" -o jsonpath='{.status.failed}')"
  if [[ "${succeeded:-0}" -ge 1 ]]; then
    log "job/${job_name} succeeded"
    exit 0
  fi
  if [[ "${failed:-0}" -ge 1 ]]; then
    die "job/${job_name} failed. Inspect it with: kubectl --kubeconfig ${LOCAL_KUBECONFIG#"${REPO_ROOT}/"} -n ${NAMESPACE} describe job ${job_name}"
  fi
  sleep 2
done
die "job/${job_name} did not finish within ${JOB_TIMEOUT_SECONDS}s"
