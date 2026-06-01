# 미국주식 장기 투자 스캐너 v4.11.1

나스닥/S&P500 ~500종목 자동 스캔 · 월간 리밸런싱 · 텔레그램 알림 · 웹 대시보드

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **월 1회 자동 리밸런싱** | 모멘텀(40pt) + 재무(40pt) + 기술적(20pt) 복합 스코어로 상위 10종목 선정 |
| **MA200 필터** | 200일 이동평균선 위 종목만 편입 |
| **VIX 레짐 대응** | VIX ≥30 → 현금 50%, VIX ≥40 → 현금 60% 자동 조절 |
| **스톱로스 경보** | 진입가 대비 -20% 이하 종목 텔레그램 즉시 알림 |
| **MDD 모니터링** | 포트폴리오 최대낙폭 추적 |
| **텔레그램 양방향** | `/status` `/scan` `/perf` `/help` 명령어 지원 |
| **웹 대시보드** | FastAPI SPA — 홈/포트폴리오/성과/리스크/변경내역/로그/로드맵 탭 |

---

## 파일 구성

```
├── longterm_scanner_v4.11.py   ← 봇 본체 (v4.11.1)
├── dashboard.py                ← FastAPI 웹 대시보드
├── dashboard_data.py           ← 대시보드 데이터 헬퍼
├── dashboard.service           ← 대시보드 systemd 서비스
├── stock_scanner_us.service    ← 봇 systemd 서비스
├── scanner/                    ← 모듈 패키지 (리팩토링)
│   ├── config.py               ← 전략 파라미터
│   ├── scoring.py              ← 스코어링 로직
│   ├── portfolio.py            ← 포트폴리오 관리
│   ├── rebalancing.py          ← 리밸런싱 로직
│   ├── performance.py          ← 성과 추적
│   ├── alerts.py               ← 스톱로스/드리프트 경보
│   ├── telegram_io.py          ← 텔레그램 송수신
│   ├── data.py                 ← yfinance 데이터 로딩
│   ├── universe.py             ← 유니버스 관리
│   └── scheduler.py            ← 스케줄러
├── tests/                      ← 단위 테스트
├── requirements.txt            ← 봇 패키지
├── requirements_dashboard.txt  ← 대시보드 패키지
├── env.example                 ← 환경변수 템플릿
├── manage.sh                   ← 서버 관리 스크립트
└── README.md
```

---

## 빠른 시작

### 1. 파일 배포

```bash
git clone https://github.com/PeterPark3832/Nasdaq_S-P500_Longterm_Portfolio_Scanner.git /root/us_longterm_bot
cd /root/us_longterm_bot
```

### 2. 환경변수 설정

```bash
cp env.example .env
nano .env
```

| 변수 | 설명 |
|------|------|
| `TELEGRAM_TOKEN` | BotFather에서 발급한 봇 토큰 |
| `TELEGRAM_CHAT_IDS` | 알림 채팅방 ID (콤마 구분, 여러 개 가능) |
| `TELEGRAM_TOPIC_ID` | 포럼 그룹 토픽 ID (선택) |
| `DASHBOARD_TOKEN` | 대시보드 접근 토큰 (기본값: `scanner2024`) |

> 채팅방 ID 확인: `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속 후 봇에 메시지 전송

### 3. 설치 및 시작

```bash
bash manage.sh install   # 가상환경 + 패키지 설치 + systemd 등록
bash manage.sh start     # 봇 시작
```

대시보드 별도 시작:
```bash
systemctl start us-longterm-dashboard   # 포트 8502
```

---

## 관리 명령어

```bash
bash manage.sh status      # 실행 상태
bash manage.sh log         # 최근 로그 50줄
bash manage.sh log live    # 실시간 로그 (Ctrl+C 종료)
bash manage.sh portfolio   # 현재 포트폴리오 출력
bash manage.sh restart     # 재시작
bash manage.sh stop        # 중지
bash manage.sh rebal       # 강제 리밸런싱 재실행
```

### 텔레그램 명령어

| 명령어 | 설명 |
|--------|------|
| `/status` | 포트폴리오 현황 + 수익률 + 낙폭 즉시 조회 |
| `/scan` | 수동 리밸런싱 강제 실행 (평일만) |
| `/perf` | 성과 점검 즉시 실행 (벤치마크 비교) |
| `/help` | 명령어 목록 |

---

## 웹 대시보드

`http://<서버IP>:8502/?token=<DASHBOARD_TOKEN>` 접속

| 탭 | 내용 |
|----|------|
| 🏠 홈 | KPI 5개 + 성과 차트(포트폴리오/SPY/QQQ) + 보유 종목 |
| 📊 포트폴리오 | 섹터 도넛 차트 + 종목 상세 테이블 |
| 📈 성과 분석 | 누적 수익률 차트 + 성과 이력 테이블 |
| ⚠️ 리스크 | MDD 게이지 + VIX 레짐 + 스톱로스 가격표 |
| 🔄 변경 내역 | 월별 리밸런싱 신규편입/편출/비중변화 카드뷰 |
| 📋 로그 | 실시간 봇 로그 조회 (에러/INFO 필터) |
| 🗺️ 로드맵 | 개발 계획 및 현황 |

### 대시보드 API

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/data?token=` | 포트폴리오 + 성과 데이터 |
| `GET /api/changes?token=` | 최근 리밸런싱 변경 내역 |
| `GET /api/logs?token=&n=300` | 봇 로그 최근 N줄 |

---

## 스케줄 (KST 기준)

| 시간 | 동작 |
|------|------|
| 매일 07:00 | Heartbeat — 전일 종가 기준 수익률 + 스톱로스 점검 |
| 매월 15일 07:00 | 중간 성과 점검 브리핑 |
| 매일 07:10 | 리밸런싱 체크 (당월 미실행 시 즉시 실행) |

---

## 전략 파라미터

`longterm_scanner_v4.11.py` → `STRATEGY` 딕셔너리:

```python
STRATEGY = {
    "portfolio_size":        10,      # 보유 종목 수
    "safe_asset_weight":     30.0,    # 기본 현금 비중 %
    "use_ma200":             True,    # MA200 필터
    "stoploss_threshold":   -0.20,    # 개별 스톱로스 -20%
    "drift_alert_threshold": 10.0,    # 드리프트 경보 ±10%p
    "vix_caution":           30,      # VIX 주의 임계값 → 현금 50%
    "vix_fear":              40,      # VIX 공포 임계값 → 현금 60%
    "max_workers":           8,       # 병렬 스레드
}
```

---

## 생성 파일

서버 실행 후 자동 생성되는 파일 (`.gitignore` 제외):

| 파일 | 설명 |
|------|------|
| `longterm_scanner_us.log` | 실행 로그 |
| `portfolio_state_us.json` | 현재 포트폴리오 (진입가·비중·날짜) |
| `portfolio_prev_us.json` | 이전 달 포트폴리오 (변경 내역 비교용) |
| `rebalancing_changes.json` | 최근 리밸런싱 변경 내역 (대시보드용) |
| `last_rebal_us.json` | 당월 리밸런싱 완료 기록 |
| `performance_history.json` | 성과 이력 |
| `yf_info_cache.json` | yfinance 재무 캐시 (당월 재사용) |
| `universe_snapshots/` | 월별 유니버스 스냅샷 |

---

## 버전 이력

| 버전 | 주요 변경 |
|------|-----------|
| **v4.11.1** | 텔레그램 한글 청크 버그 수정 (bytes 기준), 리밸런싱 변경 내역 저장, 이전 포트폴리오 백업, 대시보드 변경내역/로그/로드맵 탭 추가 |
| v4.11 | 스톱로스 월 단위 리셋, Watchdog 스레드, 텔레그램 Long-polling 안정성 개선 |
| v4.10 | VIX 레짐 기반 현금 비중 자동 조절 |
| v4.9 | 텔레그램 명령어 응답 채팅방 분리 (`_reply_to`) |
| v4.8 | MDD 기준 수익률 float 반환, Heartbeat 개선 |
| v4.7 | 성과 이력 저장 (`performance_history.json`) |

---

## 주의사항

1. **첫 실행 소요 시간** — 유니버스 ~500종목 조회로 10~20분 소요
2. **yfinance Rate Limit** — 잦은 재시작 시 IP 차단 가능, 재시작 간격 최소 5분 권장
3. **재무 미래참조 편향** — yfinance.info는 현재 재무값 제공, 백테스트 수치는 참고용
4. **상장폐지 종목** — M&A/상폐로 유니버스에 잔류하는 종목은 에러 로그 후 자동 제외

---

## 트러블슈팅

```bash
# 봇이 시작하자마자 죽는 경우
bash manage.sh log

# 리밸런싱이 안 돌 때
bash manage.sh rebal

# .env 값 변경 후
bash manage.sh restart

# yfinance 연결 확인
/root/us_longterm_bot/venv/bin/python -c "import yfinance as yf; print(yf.download('AAPL', period='5d', progress=False))"

# 대시보드 재시작
systemctl restart us-longterm-dashboard
```
