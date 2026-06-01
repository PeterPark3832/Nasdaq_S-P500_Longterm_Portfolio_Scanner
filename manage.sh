#!/bin/bash
# =============================================
# 미국주식 스캐너 v4.11 — 서버 관리 스크립트
# 사용법: bash manage.sh [명령어]
# =============================================

SERVICE="stock_scanner_us"
DASHBOARD_SERVICE="portfolio_dashboard"
BOT_DIR="/root/swing_bot"
VENV_DIR="$BOT_DIR/venv"
BOT_FILE="$BOT_DIR/longterm_scanner_v4.11.py"
LOG_FILE="$BOT_DIR/longterm_scanner_us.log"

# 색상 출력
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ──────────────────────────────────────────────
# 명령어 분기
# ──────────────────────────────────────────────
case "$1" in

  # ── 최초 설치 ────────────────────────────────
  install)
    info "=== 미국주식 스캐너 v4.0 설치 시작 ==="

    # 1. 시스템 패키지
    info "시스템 패키지 설치..."
    apt-get update -q && apt-get install -y python3 python3-pip python3-venv -q

    # 2. 작업 디렉토리
    info "작업 디렉토리 확인: $BOT_DIR"
    mkdir -p "$BOT_DIR"
    cd "$BOT_DIR"

    # 3. 가상환경 생성
    if [ ! -d "$VENV_DIR" ]; then
      info "가상환경 생성..."
      python3 -m venv venv
    else
      info "가상환경 이미 존재 — 재사용"
    fi

    # 4. 패키지 설치
    info "Python 패키지 설치..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$BOT_DIR/requirements.txt"

    # 5. .env 파일 확인
    if [ ! -f "$BOT_DIR/.env" ]; then
      warn ".env 파일이 없습니다!"
      info ".env.example을 복사하고 값을 채워주세요:"
      echo "  cp $BOT_DIR/.env.example $BOT_DIR/.env"
      echo "  nano $BOT_DIR/.env"
    else
      info ".env 파일 확인됨"
    fi

    # 6. systemd 서비스 등록
    info "systemd 서비스 등록..."
    cp "$BOT_DIR/stock_scanner_us.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable "$SERVICE"

    info "=== 설치 완료 ==="
    echo ""
    echo "다음 단계:"
    echo "  1. .env 파일에 TELEGRAM_TOKEN, TELEGRAM_CHAT_IDS 입력"
    echo "  2. bash manage.sh start"
    ;;

  # ── 시작 ─────────────────────────────────────
  start)
    if [ ! -f "$BOT_DIR/.env" ]; then
      error ".env 파일이 없습니다. 먼저 설정하세요."
      exit 1
    fi
    info "봇 시작..."
    systemctl start "$SERVICE"
    sleep 2
    systemctl status "$SERVICE" --no-pager | head -20
    ;;

  # ── 중지 ─────────────────────────────────────
  stop)
    info "봇 중지..."
    systemctl stop "$SERVICE"
    info "중지 완료"
    ;;

  # ── 재시작 ───────────────────────────────────
  restart)
    info "봇 재시작..."
    systemctl restart "$SERVICE"
    sleep 2
    systemctl status "$SERVICE" --no-pager | head -10
    ;;

  # ── 상태 확인 ─────────────────────────────────
  status)
    systemctl status "$SERVICE" --no-pager
    echo ""
    if systemctl is-active --quiet "$SERVICE"; then
      info "봇이 실행 중입니다 ✅"
    else
      warn "봇이 실행 중이지 않습니다 ❌"
    fi
    ;;

  # ── 로그 ─────────────────────────────────────
  log)
    if [ "$2" == "live" ]; then
      info "실시간 로그 (Ctrl+C로 종료)..."
      tail -f "$LOG_FILE"
    else
      info "최근 50줄 로그:"
      tail -50 "$LOG_FILE"
    fi
    ;;

  # ── 포트폴리오 확인 ──────────────────────────
  portfolio)
    PFILE="$BOT_DIR/portfolio_state_us.json"
    if [ ! -f "$PFILE" ]; then
      warn "포트폴리오 파일 없음 (아직 리밸런싱 미실행)"
    else
      info "=== 현재 포트폴리오 ==="
      python3 -c "
import json
data = json.load(open('$PFILE', encoding='utf-8'))
print(f'리밸런싱 월: {data[\"month\"]}')
print(f'{'티커':<10} {'이름':<25} {'비중':>6} {'진입가':>10} {'진입일':<12}')
print('-' * 70)
for h in data['holdings']:
    t = h['ticker']
    n = h['name'][:24]
    w = h['weight']
    p = h['entry_price']
    d = h['entry_date']
    if t == 'CASH':
        print(f'{t:<10} {n:<25} {w:>5.1f}%  {'현금':>10}  {d:<12}')
    else:
        print(f'{t:<10} {n:<25} {w:>5.1f}%  \${p:>9.2f}  {d:<12}')
"
    fi
    ;;

  # ── 강제 리밸런싱 ────────────────────────────
  rebal)
    warn "당월 리밸런싱 기록을 초기화합니다 (강제 재실행)"
    read -p "계속하시겠습니까? (y/N): " confirm
    if [ "$confirm" == "y" ] || [ "$confirm" == "Y" ]; then
      rm -f "$BOT_DIR/last_rebal_us.json"
      info "기록 초기화 완료. 봇 재시작 후 즉시 리밸런싱이 실행됩니다."
      bash "$0" restart
    else
      info "취소됨"
    fi
    ;;

  # ── 대시보드 설치 ─────────────────────────────
  dashboard-install)
    info "=== 대시보드 설치 ==="
    info "FastAPI 패키지 설치..."
    "$VENV_DIR/bin/pip" install -r "$BOT_DIR/requirements_dashboard.txt" -q
    info "systemd 서비스 등록..."
    cp "$BOT_DIR/dashboard.service" /etc/systemd/system/"$DASHBOARD_SERVICE".service
    systemctl daemon-reload
    systemctl enable "$DASHBOARD_SERVICE"
    systemctl start "$DASHBOARD_SERVICE"
    sleep 2
    systemctl status "$DASHBOARD_SERVICE" --no-pager | head -10
    local_ip=$(hostname -I | awk '{print $1}')
    info "대시보드 접속: http://${local_ip}:8502/?token=scanner2024"
    ;;

  # ── 대시보드 시작/중지/재시작/상태 ──────────
  dashboard)
    case "$2" in
      start)   systemctl start "$DASHBOARD_SERVICE"   && info "대시보드 시작됨" ;;
      stop)    systemctl stop "$DASHBOARD_SERVICE"    && info "대시보드 중지됨" ;;
      restart) systemctl restart "$DASHBOARD_SERVICE" && info "대시보드 재시작됨" ;;
      status)  systemctl status "$DASHBOARD_SERVICE" --no-pager ;;
      *)
        info "사용법: bash manage.sh dashboard [start|stop|restart|status]"
        ;;
    esac
    ;;

  # ── 업데이트 ─────────────────────────────────
  update)
    info "봇 파일 업데이트..."
    warn "longterm_scanner_v4.11.py 파일을 $BOT_DIR 에 복사 후 restart 하세요"
    echo "  cp /path/to/longterm_scanner_v4.11.py $BOT_DIR/"
    echo "  bash manage.sh restart"
    ;;

  # ── 도움말 ───────────────────────────────────
  *)
    echo ""
    echo "사용법: bash manage.sh [명령어]"
    echo ""
    echo "  install             최초 설치 (가상환경 + 패키지 + systemd 등록)"
    echo "  start               봇 시작"
    echo "  stop                봇 중지"
    echo "  restart             봇 재시작"
    echo "  status              실행 상태 확인"
    echo "  log                 최근 로그 50줄 출력"
    echo "  log live            실시간 로그 스트리밍"
    echo "  portfolio           현재 포트폴리오 출력"
    echo "  rebal               강제 리밸런싱 재실행"
    echo "  update              업데이트 방법 안내"
    echo ""
    echo "  dashboard-install   대시보드 최초 설치 (FastAPI + systemd 등록)"
    echo "  dashboard start     대시보드 시작"
    echo "  dashboard stop      대시보드 중지"
    echo "  dashboard restart   대시보드 재시작"
    echo "  dashboard status    대시보드 상태 확인"
    echo ""
    ;;
esac
