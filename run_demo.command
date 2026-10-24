#!/bin/zsh
unsetopt BGNICE
cd "$(dirname "$0")" || exit 1
export DEVELOPMENT_MODE=True
if [[ ! -x .venv/bin/python ]]; then
  echo "프로젝트의 .venv가 없습니다. 가상환경과 패키지를 먼저 설치해주세요."
  exit 1
fi
.venv/bin/python - <<'PY'
import socket
for port in (8000, 8501):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'{port} 포트가 사용 중입니다. 기존 FastAPI/Streamlit 터미널에서 Ctrl+C 후 다시 실행해주세요.')
PY
if [[ $? -ne 0 ]]; then exit 1; fi
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
backend_pid=$!
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null' EXIT
trap 'exit 0' INT TERM
echo "개발자 시연: http://127.0.0.1:8501 · woodglue 계정으로 로그인하세요."
echo "종료: Ctrl+C · 이 컴퓨터에서만 접속할 수 있습니다."
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done
