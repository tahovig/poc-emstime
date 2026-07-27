#!/usr/bin/env bash
# Launch poc-emstime's dev servers (backend + frontend) in a tmux session,
# replacing the ad-hoc backgrounded-process-plus-log-file approach.
# Usage: ./dev-tmux.sh [session-name]
# Attaches if the session is already running; otherwise creates it fresh
# with three windows: backend (uvicorn --reload), frontend (vite dev
# server), and a free shell.
set -euo pipefail
cd "$(dirname "$0")"

SESSION="${1:-poc-emstime}"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already running -- attaching."
  exec tmux attach-session -t "$SESSION"
fi

tmux new-session -d -s "$SESSION" -n backend \
  "source poc-emstime-venv/bin/activate && uvicorn poc_emstime.app.main:app --reload --port 8000"

tmux new-window -t "$SESSION" -n frontend "cd frontend && npm run dev"

tmux new-window -t "$SESSION" -n shell

tmux select-window -t "$SESSION:shell"
exec tmux attach-session -t "$SESSION"
