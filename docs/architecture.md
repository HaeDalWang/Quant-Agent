# 아키텍처

## 설계 철학

이 시스템의 중심 통찰: **LLM은 알림 채널을 읽고 판단하지 않는다. LLM은 데이터 저장소를 읽는다.**
따라서 가장 중요한 것은 깨끗하고 구조화된 **데이터 레이어**다. Discord/Telegram 같은 채널은
사람에게 보내는 *출력*이자 나중에 사람이 봇에게 명령하는 *입력*일 뿐, 에이전트의 추론 소스가 아니다.

이 원칙이 레이어 분리를 결정한다.

## 레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│  Phase 4: Execution      실매매 (승인 게이트, 소액)         │
├─────────────────────────────────────────────────────────┤
│  Phase 3: Agent Group    멀티에이전트 토론·합의             │
├─────────────────────────────────────────────────────────┤
│  Phase 2: Agent          단일 LLM 관찰·판단·제안 (paper)    │
├═════════════════════════════════════════════════════════┤  ← AI 경계
│  Phase 1: Intelligence   분석 · 규칙 알림 · 정기 리포트      │
├─────────────────────────────────────────────────────────┤
│  Phase 0: Foundation     수집 · 저장 · 스케줄              │
└─────────────────────────────────────────────────────────┘
        모든 상위 레이어는 아래 레이어의 "산출물"만 소비한다.
```

핵심: **AI 경계 아래는 결정론적**이다. 같은 입력이면 같은 출력. 이게 보장돼야 위에서 AI가 무엇을 보고 판단했는지 재현·감사할 수 있다.

## 디렉토리 구조 (현행 + 목표)

> `src/quant_agent/` 아래. (목표)는 아직 미구현, 나머지는 구현됨.

```text
quant-agent/
├── collectors/          # 데이터 수집 — 소스별 구현, 공통 인터페이스 뒤에
│   ├── base.py          # Collector 추상 인터페이스 (Repository 패턴)
│   ├── price.py         # FinanceDataReader 어댑터 (KR+US 시세)
│   ├── disclosure.py    # (목표) DART 공시 (KR)
│   └── news.py          # (목표) 뉴스/RSS
├── storage/             # 시계열 저장 추상화
│   ├── base.py          # Store 인터페이스
│   └── duckdb_store.py   # DuckDB 구현체
├── analysis/            # 지표 계산 (순수 함수, 불변 입출력)
│   ├── indicators.py    # 이동평균/RSI/MACD/ATR (pandas 내장 직접 구현)
│   └── signals.py       # 지표 → 신호 변환 (최신봉 스냅샷)
├── alerts/              # 알림
│   ├── base.py          # AlertChannel 인터페이스 + Alert 값객체
│   ├── console.py       # 콘솔 채널 (기본·테스트, 네트워크 무관)
│   ├── discord.py       # Discord webhook 구현체
│   ├── factory.py       # 설정 기반 채널 선택 (webhook 있으면 Discord)
│   └── rules.py         # 규칙 엔진 (조건 → 알림 트리거)
├── reports/             # 정기 리포트 생성 (마크다운) + 포트폴리오 섹션
├── universe/            # 종목 유니버스 관리
│   ├── models.py        # Market/Symbol 값객체
│   ├── tiers.py         # Tier 1 코어 (수동 큐레이션)
│   └── screener.py      # (목표) Tier 2 조건 기반 동적 스캔
├── broker/              # 증권 계좌 추상화 (읽기 전용)
│   └── base.py          # Broker 인터페이스 + Account/Position 값객체
├── secrets/             # 시크릿 백엔드 추상화
│   ├── base.py          # SecretProvider 인터페이스
│   ├── env_provider.py  # .env 패스스루 (로컬 기본)
│   ├── aws_provider.py  # AWS Secrets Manager (optional extra)
│   └── bootstrap.py     # 백엔드 선택 → 환경 주입 → Settings 로드
├── service/             # 수집·분석 오케스트레이션 (장애 격리)
│   ├── collection.py    # 수집 (trailing overlap 자가 교정)
│   └── analysis.py      # 분석 → 알림/리포트 와이어링
├── scheduler/           # CLI 진입점 + 잡 정의 (collect/analyze/daily/run)
├── config/              # Settings(pydantic) + 로깅 설정
├── agents/              # (목표, Phase 2+) LLM 에이전트
└── data/                # DuckDB 파일, 캐시 (gitignore)
```

## 핵심 추상화 인터페이스

세 개의 인터페이스가 시스템의 교체 가능성을 책임진다. 모두 Repository 패턴.

### 1. Collector — 데이터가 어디서 오는가
```
Collector
  ├─ fetch(symbol, start, end) -> DataFrame   # 불변 반환
  └─ supports(market) -> bool                 # KR / US
```
FinanceDataReader가 KR+US를 단일 어댑터로 처리. 나중에 KIS/Alpaca를 추가해도 인터페이스 불변.

### 2. Store — 데이터가 어디에 쌓이는가
```
Store
  ├─ upsert(table, df)                # 멱등 저장
  ├─ query(sql | spec) -> DataFrame
  └─ latest(symbol, field) -> value
```
초기 DuckDB. 규모가 커지면 TimescaleDB 등으로 교체해도 상위 레이어 영향 없음.

### 3. AlertChannel — 사람에게 어떻게 전달하는가
```
AlertChannel
  ├─ send(message)                    # 텍스트 알림
  ├─ send_report(report)              # 리포트 전송
  └─ (Phase 4) request_approval(proposal) -> decision   # 승인 게이트
```
Discord 첫 구현. `request_approval`은 Discord 버튼 컴포넌트로 자연스럽게 확장된다.

## 데이터 흐름 (Phase 0~1)

```
        ┌──────────── scheduler (APScheduler) ────────────┐
        │  장마감 후 / 정해진 주기로 잡 트리거             │
        └──────────────────────┬──────────────────────────┘
                               ▼
   universe.tiers ──► collectors ──► storage (DuckDB)
   (추적 종목 결정)    (시세/공시/뉴스)    (불변 시계열)
                                            │
                                            ▼
                                       analysis
                                  (지표 계산 → 신호)
                                            │
                          ┌─────────────────┴─────────────────┐
                          ▼                                   ▼
                    alerts.rules                         reports
                 (조건 충족 → 트리거)                  (정기 종합)
                          │                                   │
                          └────────────► AlertChannel ◄───────┘
                                          (Discord)
```

## 채널 선택 근거: 왜 Discord인가

LLM 미래 기능 관점에서 Discord가 Telegram보다 유리한 지점:

| 미래 기능 | Discord | Telegram |
|----------|---------|----------|
| 승인 게이트 (Phase 4) | 버튼 컴포넌트 네이티브 | 인라인 키보드 (투박) |
| 멀티에이전트 토론 시각화 (Phase 3) | 웹훅별 페르소나+아바타, 종목별 스레드 | 단일 봇, 스레드 약함 |
| 검색 가능 히스토리 (RAG 소스) | 강함 | 약함 |

단, 채널은 `AlertChannel` 뒤에 있으므로 언제든 교체 가능. 결정을 잠그지 않는다.

## 비기능 요구사항

- **재현성**: AI 경계 아래는 결정론적. 잡 실행은 멱등(idempotent)하게.
- **장애 격리**: 한 종목 수집 실패가 전체 파이프라인을 죽이지 않는다. 수집·분석 모두 종목 단위로 격리.
- **시크릿 관리**: `secrets/` 추상화로 로컬(.env)·클라우드(AWS Secrets Manager)를 한 인터페이스 뒤에 둠. 절대 커밋 금지, 시작 시 필수 시크릿 검증.
- **자가 교정**: 수집은 매번 최근 N일을 겹쳐 재수집(trailing overlap) — 장초반 잠정 거래량을 확정값으로 덮어쓴다(멱등 upsert).
- **레이트 리밋**: 외부 API 호출 재시도·백오프는 미구현(목표). 현재는 종목 단위 격리로 부분 실패를 흡수.
- **관측성**: 모든 잡은 시작/종료/실패를 구조화 로그로 남긴다 (나중에 에이전트 컨텍스트로도 활용).
