#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo "먼저 프로젝트 가상환경을 준비해주세요."
  exit 1
fi
# 기존 run_demo.command의 FastAPI가 실행 중이어야 합니다.
.venv/bin/python phone_test.py
