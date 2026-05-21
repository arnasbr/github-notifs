#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "First run: setting up venv..."
    python3 -m venv venv
    ./venv/bin/pip install -q -r requirements.txt
fi

trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM

./venv/bin/python notifier.py &
./venv/bin/python app.py &

echo "gh-notify running -> http://127.0.0.1:5000  (ctrl-c to stop)"
wait -n
