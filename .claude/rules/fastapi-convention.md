

# Code Style (Python / FastAPI)

## 기본
- 포맷/린트: ruff (format + check). PEP 8, snake_case 준수
- 모든 함수/메서드에 타입 힌트 필수. 반환 타입도 명시
- docstring은 Google 스타일. public 함수와 port 인터페이스에만 작성, 자명한 코드엔 생략
- 주석은 "왜"를 설명할 때만. "무엇"을 설명하는 주석은 코드로 대체

## 네이밍
- 축약 금지: `usr` → `user`, `res` → `response`, `cnt` → `count`
- 함수/메서드는 동사로 시작하고 의도가 드러나게: `find_by_id`, `create_order`, `send_notification`
- bool 변수/함수는 의문형: `is_active`, `has_permission`, `should_retry`, `can_edit`
- 컬렉션은 복수형: `users`, `order_ids`
- 클래스는 PascalCase, 상수는 UPPER_SNAKE_CASE

## FastAPI
- 라우터는 도메인별 `APIRouter`로 분리, `main.py`에서 include
- 요청/응답 모델은 pydantic v2 (`BaseModel`, `model_config`, `Field`). ORM/도메인 객체를 직접 응답으로 노출하지 않음
- 예외는 `HTTPException`을 상속한 커스텀 예외 계층 사용, 직접 `HTTPException(...)` raise 금지
- 의존성 주입은 `Depends`로. 서비스/리포지토리를 라우터에서 직접 생성하지 않음
- `async def`와 `def`는 상황에 따라 적절하게 쓴다

## 아키텍처: 헥사고날
```
src/<bounded_context>/
├── domain/ # 순수 파이썬 객체(dataclass/pydantic), 프레임워크 의존 없음
├── application/
│ ├── ports/ # inbound(use case) / outbound(repository, client) 인터페이스 (Protocol)
│ └── services/ # use case 구현, port에만 의존
└── adapters/
├── inbound/ # FastAPI 라우터, 스케줄러 등
└── outbound/ # DB, 외부 API 클라이언트 구현
```

- 의존 방향: adapters → application → domain. 역방향 import 금지
- domain은 FastAPI/SQLAlchemy 등 프레임워크를 import하지 않음
- port는 `Protocol` 또는 `ABC`로 정의하고 메서드마다 한 줄 docstring
- inbound/outbound가 커지면 하위 패키지로 분리 가능 (`adapters/outbound/persistence/`, `adapters/outbound/external/`)

### 계층별 책임
- **Router (inbound adapter)**: 요청 파싱/검증 → 서비스 호출 → 응답 변환. 이게 전부.
  - if/for 같은 분기·반복 로직, 리포지토리 직접 호출, 계산 로직 금지
  - 라우터 함수 본문이 5줄을 넘으면 로직이 새고 있는 것. 서비스 혹은 데코레이터 등 다른 계층으로 내려보낼 것
- **Service (application)**: use case 오케스트레이션만 담당
  - 하는 일: 리포지토리에서 도메인 객체 조회 → 도메인 메서드 호출 → 저장 → 결과 반환. 트랜잭션 경계도 여기
  - 하지 않는 일: 비즈니스 규칙 판단, 상태 계산, 검증 로직. 이건 전부 도메인으로
  - 서비스에 `if order.status == "PAID" and order.amount > 1000:` 같은 코드가 보이면 `order.can_refund()`로 도메인에 옮길 것
- **Domain**: 비즈니스 규칙과 상태 변경의 주인
  - 객체가 자기 데이터로 스스로 판단하고 행동하게 작성 (Tell, Don't Ask)
  - getter로 값을 꺼내 외부에서 판단하지 말고, 판단 자체를 도메인 메서드로: `if user.is_adult()` (O) / `if user.age >= 19` (X)
  - 상태 변경은 도메인 메서드를 통해서만: `order.cancel()` (O) / `order.status = "CANCELLED"` (X)
  - 불변식 위반은 도메인 예외로 raise. 서비스가 이를 HTTP 예외로 변환
  - 데이터만 들고 메서드가 없는 도메인 클래스(빈약한 도메인 모델)는 작성하지 않음

## 테스트
- pytest + pytest-asyncio. 파일명 `test_*.py`, 함수명 `test_<대상>_<조건>_<기대결과>`
- 도메인 테스트는 순수 단위 테스트로, 외부 의존 없이 작성. 비즈니스 규칙 테스트는 대부분 여기에 위치
- 서비스 테스트는 port를 fake/mock으로 대체해 프레임워크 없이 실행




