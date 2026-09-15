# retail-ontology-log-pipeline

리테일 POS 로그로 공급망 온톨로지를 만들고, 공급 중단의 영향을 근거와 함께 설명하는 챗봇까지 구축하는 개인 학습 프로젝트입니다. 배포하지 않고 로컬 Kubernetes에서만 실행합니다.

- 주제와 전체 구조: [docs/architecture.md](docs/architecture.md)
- 기술 결정 기록: [docs/adr](docs/adr/README.md)
- 실행과 종료 방법: [docs/guides/local-environment.md](docs/guides/local-environment.md)
- 1차 스프린트 보고서: [docs/reports/sprint-01-report.md](docs/reports/sprint-01-report.md)

## 빠른 시작

필요한 도구와 Docker 자원을 확인합니다.

```bash
make doctor
```

로컬 클러스터를 만들고 PostgreSQL, SeaweedFS, Lakekeeper를 배포한 뒤 레이크하우스를 초기화합니다.

```bash
make up
```

실제 데이터를 내려받습니다. Kaggle API 토큰이 필요하며, 설정 방법은 가이드에 있습니다.

```bash
make data-download
```

원천 파일을 raw 영역과 Iceberg bronze 테이블에 적재하고 행 수를 검증합니다.

```bash
make ingest DATASET=dunnhumby
```

작업을 마치면 데이터를 유지한 채 클러스터를 멈춥니다.

```bash
make stop
```

모든 명령은 저장소 안의 `.kube/retail-ontology.yaml`만 사용하므로, 셸의 기본 kube context는 바뀌지 않습니다.

## 저장소 구조

| 경로 | 내용 |
|---|---|
| `data-pipeline/` | 원천 적재와 변환 파이프라인 (Python) |
| `deploy/` | k3d 클러스터 설정, helmfile, 로컬 Helm 차트와 values |
| `scripts/` | Makefile이 호출하는 클러스터·인프라·Job 스크립트 |
| `docs/` | 아키텍처, ADR, 가이드, 스프린트 계획과 보고서 |
| `data/` | 내려받거나 생성한 원천 파일 (git 제외) |
| `.local/`, `.kube/` | 로컬 자격 증명, Helm 캐시, kubeconfig (git 제외) |
