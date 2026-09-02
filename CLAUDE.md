# CLAUDE.md

미국주식 장기투자 스캐너 — **단일 사용자용** 텔레그램 봇 + 토큰 인증 웹 대시보드.
VPS 1대에 systemd 2개(봇 + 대시보드)로 배포되어 실제 운영 중.

> **다중 사용자 웹앱 "시드앤그로우(SeedNGrow)"는 이 리포가 아니다.**
> `../SeedNGrow`(github.com/PeterPark3832/seedngrow)로 독립했다. 2026-06 시점에 이 폴더에서
> 시작했던 흔적(`dashboard_app/`, `db/`, `auth/`, `strategies/`, `migrations/`, `alembic.ini`,
> `app.db`, 관련 테스트 11개)이 남아 있었으나 2026-09-02에 전부 삭제했다. 그 작업은 저쪽
> 리포에서만 진행할 것. 여기서 그 파일들을 다시 만들지 말 것.

---

## 프로덕션 실체

배포 서버: `158.247.223.231`, 디렉터리 `/root/us_longterm_bot`, venv Python 3.12.3.

| systemd 유닛 | 실행 파일 | 비고 |
|---|---|---|
| `us-longterm-bot.service` | `longterm_scanner_v4.11.py` | 스캐너 봇 본체 |
| `us-longterm-dashboard.service` | `dashboard.py` | 웹 대시보드, `0.0.0.0:8502` |

같은 서버에 **무관한 다른 프로젝트**가 함께 돈다(`/root/stock-scanner` → `stock-scanner`,
`stock-dashboard`, 한국주식 눌림목 자동매매). 건드리지 말 것.

### 리포 ↔ 서버 불일치 (작업 전 반드시 인지)

- **서버는 git clone이 아니다.** 배포 = sftp 수동 복사. 그래서 서버 파일이 리포보다 앞서 있을
  수 있다. 실제로 `longterm_scanner_v4.11.py`는 서버본(110,392B)과 리포본이 **다르다**.
  → **배포 전 `md5sum` 비교 필수.** 다르면 파일을 통째로 덮어쓰지 말고 서버 사본에 문자열
  치환으로 국소 패치할 것.
- **`manage.sh`와 `stock_scanner_us.service`는 프로덕션과 맞지 않는다.** 이들이 가리키는
  `/root/swing_bot` 디렉터리도, `stock_scanner_us`·`portfolio_dashboard` 유닛도 서버에 **없다**.
  → `manage.sh` 명령을 그대로 쓰지 말고 `systemctl`을 직접 쓸 것.
  (`dashboard.service`만 실제 경로와 일치한다.)
- 서버에는 리포에 없는 `dashboard_data.py`가 있지만 아무 데서도 import되지 않는 고아 파일이다.

```bash
systemctl status  us-longterm-dashboard
systemctl restart us-longterm-bot
journalctl -u us-longterm-dashboard --since '10 minutes ago' --no-pager
```

---

## 코드 구조

- **`longterm_scanner_v4.11.py`** — 실제 배포되는 봇 모놀리스. `STRATEGY` 딕셔너리(종목 수 10,
  기본 현금 30%, MA200 필터, 스톱로스 -20%, VIX 30/40 → 현금 50/60%), 스케줄(KST 07:00 Heartbeat +
  성과 점검, 07:10 리밸런싱 체크), 텔레그램 명령어 long-polling·Watchdog 데몬 스레드.
- **`dashboard.py`** — FastAPI 단일 파일. 인라인 HTML/JS 문자열 패턴(빌드 스텝 없음, Jinja2 안 씀).
  인증은 쿼리파라미터 토큰(`DASHBOARD_TOKENS` 콤마 구분, 없으면 `DASHBOARD_TOKEN`, 기본
  `scanner2024`). IP별 슬라이딩 윈도우 rate limit — `/`는 30, API는 60(요청/분)이고 **버킷은 IP당
  하나를 공유**한다(리버스 프록시를 두면 전 사용자가 한 버킷을 쓰게 되니 주의. 현재는 nginx 없이
  8502 직접 노출).
- **`scanner/`** — **프로덕션에서 쓰이지 않는다.** 모놀리스를 패키지로 쪼개려던 리팩터인데 배포된
  적이 없고 서버에도 존재하지 않는다. 이걸 import하는 건 `tests/` 2개뿐.
  → **봇 동작을 바꾸려면 반드시 `longterm_scanner_v4.11.py`를 고칠 것.** `scanner/`만 고치면
  아무 일도 일어나지 않는다.
- **`longterm_portfolio_bot.py`** — QM(Quality-Momentum) 분기 전략 봇 v1.0. 어디서도 실행되지
  않고 서버에도 없다. SeedNGrow가 스코어링/백테스트를 재사용하려고 import했던 유산.
- **`tests/`** — `test_scoring.py`, `test_portfolio.py` (대상은 `scanner/`). 32개 전부 통과.

---

## 불변 규칙

### 1. 상태 JSON에 NaN을 저장하지 말 것

2026-08-31 사고: `performance_history.json`에 `portfolio_ret_pct: NaN`이 저장되면서
`/api/data`가 500을 반환 → 대시보드 본문 전체가 "데이터 로드 실패"로 죽었고 8/31~9/2 동안
방치됐다.

원인은 비대칭이다. `json.loads`는 파이썬 확장이라 bare `NaN`을 **읽어들이지만**, Starlette
`JSONResponse`는 `allow_nan=False`로 **덤프하다 터진다**. 값 하나만 섞여도 응답 전체가 500이다.
NaN의 출처는 상장폐지·거래정지 종목에 yfinance가 주는 NaN 종가 → `ret_pct` → `weighted_ret`.
`round(nan, 2)`는 `nan` 그대로라 걸러지지 않았다.

현재 방어는 두 겹이다:
- `longterm_scanner_v4.11.py`의 `_finite()` — 저장 시점 차단. **성과 레코드에 수치 필드를
  추가하면 반드시 `_finite()`를 통과시킬 것.**
- `dashboard.py`의 `_sanitize()` — `_load()`에서 NaN/Inf → `None` 정규화. 읽기 시점 최후 방어.

### 2. 프런트에서 에러를 삼키지 말 것

`load()`의 `catch{}`가 예외를 통째로 버려서 위 사고의 원인이 화면에 전혀 드러나지 않았다.
지금은 HTTP 상태 코드를 배너에 노출한다. `dashboard.py`에 fetch를 추가할 때 같은 패턴을 지킬 것.

### 3. `render()`는 `load()`의 try 안에서 호출된다

따라서 렌더 중 JS 예외도 "데이터 로드 실패"로 표시된다. 이 배너를 봤다고 API 실패로 단정하지 말 것.
DevTools Network에서 `/api/data` 상태 코드부터 확인한다.

---

## 상태 파일 (전부 `.gitignore`)

| 파일 | 내용 |
|---|---|
| `portfolio_state_us.json` | 현재 포트폴리오(진입가·비중·`max_equity`) |
| `portfolio_prev_us.json` | 직전 포트폴리오(변경 내역 비교용) |
| `rebalancing_changes.json` | 최근 리밸런싱 신규/편출/증감 |
| `last_rebal_us.json` | `{"month": "YYYY-MM"}` — 당월 실행 여부 플래그 |
| `performance_history.json` | 성과 이력(`rebalancing` / `performance_check` 레코드) |
| `yf_info_cache.json` | yfinance 재무 캐시(당월 재사용) |
| `universe_snapshots/` | 월별 유니버스 스냅샷 |

**봇 재시작 시 주의**: `already_ran_this_month()`가 `last_rebal_us.json`을 본다. 당월 기록이
없고 평일이면 **기동 직후 전체 스캔(10~20분)이 즉시 돌고 텔레그램이 발송된다.** 기록이 있으면
시작 알림 1건만 나간다. 재시작 전에 이 파일을 확인할 것.

---

## 로컬 개발 (Windows)

PATH의 `python`은 Windows Store 스텁이라 동작하지 않는다. 실제 인터프리터는
`C:\Users\쩡이\AppData\Local\Python\bin\python.exe`.

```bash
"C:/Users/쩡이/AppData/Local/Python/bin/python.exe" -m pytest tests/ -q   # 32 passed
"C:/Users/쩡이/AppData/Local/Python/bin/python.exe" dashboard.py          # :8502
# http://127.0.0.1:8502/?token=scanner2024
```

상태 JSON이 하나도 없어도 대시보드는 **정상 렌더된다**("0종목 + 현금 30%"). 빈 화면은 버그가 아니다.

헤드리스 확인은 Edge로 가능하다:

```bash
msedge --headless=new --disable-gpu --virtual-time-budget=15000 --dump-dom "http://127.0.0.1:8502/?token=..."
```

⚠️ **`--dump-dom` 결과에는 인라인 `<script>` 원문이 그대로 포함된다.** "데이터 로드 실패" 같은
문자열을 grep하면 화면에 렌더되지 않았는데도 소스 문자열에 매칭돼 오탐이 난다. 실제 렌더 여부는
`.main` / `#home-sub` / `.hero-return`의 **내용**으로 판단할 것.

---

## 자격증명

`sync_from_server.py`, `check_status.py`, `verify_final.py`, `verify_restart.py`, `patch_*.py`,
`fix_base.py`, `build_changes.py`, `resend_telegram.py`는 서버 root 비밀번호가 하드코딩되어 있어
`.gitignore`로 제외돼 있다. **이 리포는 PUBLIC이므로 절대 커밋 금지.** (전체 히스토리 검색 결과
비밀번호·서버 IP 유출 0건 — 확인 완료.) `.env`, `app.db*`도 동일하게 제외 대상이다.

---

## 대시보드 API

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/data?token=` | 포트폴리오 + 성과 이력 + 마지막 리밸런싱 |
| `GET /api/benchmark?token=&start=` | SPY/QQQ 일별 누적 수익률 (30분 TTL 캐시) |
| `GET /api/prices?token=` | 보유 종목 현재가 ("오늘 시작 가이드"용, 15분 TTL 캐시) |
| `GET /api/changes?token=` | 리밸런싱 변경 내역 |
| `GET /api/logs?token=&n=300` | 봇 로그 최근 N줄 (1~1000 클램프) |

토큰이 틀리면 `/`는 "접근 제한" 잠금 페이지를 반환한다 — 이건 "데이터 로드 실패"와 다른 증상이다.
