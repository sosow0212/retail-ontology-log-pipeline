# data-pipeline

원천 데이터를 레이크하우스에 적재하고 변환하는 파이프라인 모듈입니다. 1차 스프린트에서는 원천 파일을 raw 영역에 올리고, 이를 Iceberg bronze 테이블로 적재한 뒤 행 수를 검증하는 기능까지 구현했습니다.

## 구조

| 경로 | 역할 |
|---|---|
| `src/retail_pipeline/sources/` | 원천 CSV 테이블 명세 (컬럼, 타입, bronze 테이블 이름) |
| `src/retail_pipeline/ingestion/` | raw 영역 적재, bronze 적재, 행 수 검증 |
| `src/retail_pipeline/lakehouse/` | 오브젝트 스토리지, Lakekeeper 관리 API, Iceberg 카탈로그 연결 |
| `src/retail_pipeline/samples/` | 원천과 스키마가 같은 샘플 데이터 생성기 |
| `src/retail_pipeline/cli.py` | 클러스터 Job에서 실행하는 `retail-pipeline` 명령 |
| `tests/` | 로컬 파일 시스템과 SQLite 카탈로그로 실행하는 테스트 |

## 로컬 개발

```bash
make pipeline-sync
```

```bash
make pipeline-lint
```

```bash
make pipeline-test
```

클러스터에서 실행하는 방법은 [로컬 실행/종료 가이드](../docs/guides/local-environment.md)를 참고하세요.
