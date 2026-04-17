# 미국주식 장기 투자 스캐너 v4.11 — 서버 배포 가이드

나스닥/S&P500 장기 포트폴리오 자동 스캐너. 매월 리밸런싱 + 텔레그램 알림 + 개별 종목 스톱로스 경보.

## 주요 기능

- **월 1회 자동 리밸런싱** — 모멘텀 + 재무 필터로 상위 종목 선정
- **MA200 필터** — 200일 이동평균선 위 종목만 편입
- **텔레그램 양방향 제어** — `/status`, `/scan`, `/perf`, `/help` 명령어 지원
- **드리프트 경보** — 비중 ±10%p 이탈 시 즉시 알림
- **스톱로스 경보** — 진입가 대비 -20% 이하 종목 즉시 알림
- **MDD 모니터링** — 포트폴리오 최대낙폭 추적

## 파일 구성

```
├── longterm_scanner_v4.11.py  ← 봇 본체 (최신)
├── longterm_scanner_v4.*.py   ← 이전 버전 (참고용)
├── longterm_portfolio_bot.py  ← 포트폴리오 백테스트 유틸
├── requirements.txt            ← Python 패키지 목록
├── env.example                ← 환경변수 템플릿 (.env로 복사 후 값 입력)
├── stock_scanner_us.service   ← systemd 서비스 파일
├── manage.sh                  ← 서버 관리 스크립트
└── README.md
```

---

## 빠른 시작 (처음 설치)

### 1단계 — 파일 업로드

모든 파일을 서버의 `/root/swing_bot/` 디렉토리에 업로드

```bash
mkdir -p /root/swing_bot
cd /root/swing_bot
```

### 2단계 — 환경변수 설정

```bash
cp env.example .env
nano .env
```

`.env` 파일에 입력:
- `TELEGRAM_TOKEN` — BotFather에서 발급받은 봇 토큰
- `TELEGRAM_CHAT_IDS` — 알림 받을 채팅방 ID (콤마 구분)
- `TELEGRAM_TOPIC_ID` — 포럼 그룹 토픽 ID (선택)

> 채팅방 ID 확인: `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속 후 봇에 메시지 전송 → `"id"` 값

### 3단계 — 설치 및 시작

```bash
bash manage.sh install   # 가상환경 생성 + 패키지 설치 + systemd 등록
bash manage.sh start     # 봇 시작
```

### 4단계 — 텔레그램 확인

봇 시작 시 아래 메시지 수신 확인:
```
✅ 미국주식 장기 투자 스캐너 v4.11 시작
📅 당월 리밸런싱: ⏳ 즉시 실행 예정
```

---

## 일상 관리 명령어

```bash
bash manage.sh status      # 실행 상태 확인
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

## 스케줄 (KST 기준)

| 시간 | 동작 |
|------|------|
| 매일 08:50 | Heartbeat (전일 종가 기준 수익률 + 스톱로스 점검) |
| 매월 15일 08:50 | 중간 성과 점검 브리핑 |
| 매일 09:00 | 리밸런싱 체크 (당월 미실행 시 즉시 실행) |

---

## 파라미터 수정

`longterm_scanner_v4.11.py` 파일의 `STRATEGY` 딕셔너리에서 조정:

```python
STRATEGY = {
    "portfolio_size":        10,    # 보유 종목 수
    "safe_asset_weight":     30.0,  # 현금 비중 %
    "use_ma200":             True,  # MA200 위 필터
    "max_stale_days":        10,    # 거래정지 판단 기준일
    "max_workers":           8,     # 병렬 처리 스레드 수
    "stoploss_threshold":   -0.20,  # 개별 종목 스톱로스 -20%
    "drift_alert_threshold": 10.0,  # 비중 드리프트 경보 ±10%p
}
```

수정 후 재시작:
```bash
bash manage.sh restart
```

---

## 생성 파일 목록

서버 실행 후 `/root/swing_bot/` 에 생성되는 파일 (`.gitignore`로 제외됨):

| 파일 | 설명 |
|------|------|
| `longterm_scanner_us.log` | 실행 로그 |
| `portfolio_state_us.json` | 현재 포트폴리오 (진입가·비중·날짜) |
| `last_rebal_us.json` | 당월 리밸런싱 완료 기록 |
| `yf_info_cache.json` | yfinance 재무 캐시 (당월 재사용) |

---

## 주의사항

1. **한국 봇과 공존 가능** — 저장 파일명이 다르므로 같은 서버에서 동시 실행 가능
2. **첫 실행 소요 시간** — 유니버스 ~550종목 조회로 15~30분 소요
3. **yfinance Rate Limit** — 잦은 재시작 시 IP 차단 가능, 재시작 간격 최소 5분 권장
4. **재무 미래참조 편향** — yfinance.info는 현재 재무값 제공, 백테스트 수치는 참고용

---

## 트러블슈팅

### 봇이 시작하자마자 죽는 경우
```bash
bash manage.sh log
```

### .env 값을 바꿨는데 반영이 안 될 때
```bash
bash manage.sh restart
```

### 리밸런싱이 안 돌 때
```bash
bash manage.sh rebal
```

### yfinance 연결 오류
```bash
/root/swing_bot/venv/bin/python -c "import yfinance as yf; print(yf.download('AAPL', period='5d', progress=False))"
```
