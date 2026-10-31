#!/bin/sh
# Start Otto Pilot with the 3D world:  ./run.sh   (then open http://127.0.0.1:8765)
# Headless terminal only:            ./run.sh run
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
exec .venv/bin/python -m sprocket "${@:-serve}"
