#!/usr/bin/env bash
# Quant-Agent 일일 수집+분석 — cron/수동 공용
#
# cron 함정 대응:
#  1) cron은 PATH가 최소라 uv를 못 찾음 → homebrew 경로를 직접 추가
#  2) cron은 홈에서 실행됨 → 스크립트 위치(프로젝트 루트)로 이동
#  3) 화면이 없음 → 출력을 logs/daily.log에 타임스탬프와 함께 append
#
# 수동 실행:  ./daliy.sh
# cron 예시:  0 9 * * *  /Users/baeseungdo/work/Quant-Agent/daliy.sh

export PATH="/opt/homebrew/bin:$PATH"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1
mkdir -p logs

LOG="logs/daily.log"
echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily 시작 =====" >> "$LOG"
uv run quant-agent daily >> "$LOG" 2>&1
code=$?
echo "===== $(date '+%Y-%m-%d %H:%M:%S') daily 종료 (exit=$code) =====" >> "$LOG"
exit $code
