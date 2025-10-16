PY := python
VENV := .venv
PIP := $(VENV)/bin/pip
PYBIN := $(VENV)/bin/python

.PHONY: venv install check freeze run run_async smoke bench diag

venv:
	@test -d $(VENV) || python3.10 -m venv $(VENV)
	@$(PIP) install -U pip wheel

install: venv
	@$(PIP) install -U -r requirements.txt
	@echo "Installation complete. Note: PaddlePaddle may not work on Apple Silicon."

check:
	@$(PYBIN) env_check.py || (echo "env_check failed"; exit 1)

freeze:
	@$(PIP) freeze > requirements.lock.txt

run:
	@$(PYBIN) -m uvicorn app:app --reload --port 8000

run_async:
	@$(PYBIN) -m uvicorn app_async:app --reload --port 8001

smoke:
	@bash scripts/smoke.sh 8000

bench:
	@bash scripts/bench.sh

diag:
	@$(PYBIN) scripts/diag.py
