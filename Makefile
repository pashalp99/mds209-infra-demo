# Laptop-sized data stack: one command runs all five layers.
# In the airline stack this file's job is done by Cloud Composer (Airflow).

PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python
READY  := $(VENV)/.installed
SCENARIO ?= rename

.PHONY: help all pipeline capture land store transform check serve break reset

help:
	@echo "make all                       set up, simulate exports, run every layer"
	@echo "make pipeline                  rerun land → store → transform → check → serve"
	@echo "make capture|land|store|transform|check|serve   run one layer"
	@echo "make break SCENARIO=rename     also: timezone, duplicate, overwrite"
	@echo "make reset                     delete data/ and reports/ (keeps code and seeds)"

$(READY): requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --quiet -r requirements.txt
	@touch $(READY)

all: capture pipeline

pipeline: land store transform check serve

capture: $(READY)
	$(PY) -m pipeline.capture

land: $(READY)
	$(PY) -m pipeline.land

store: $(READY)
	$(PY) -m pipeline.store

transform: $(READY)
	$(PY) -m pipeline.transform

check: $(READY)
	$(PY) -m pipeline.checks

serve: $(READY)
	$(PY) -m pipeline.serve

# Rebuild from scratch, break one thing on purpose, and watch the pipeline react.
break: $(READY) reset
	$(PY) -m pipeline.capture
	@if [ "$(SCENARIO)" = "overwrite" ]; then $(PY) -m pipeline.land; fi
	$(PY) -m pipeline.break_it $(SCENARIO)
	@$(MAKE) --no-print-directory pipeline

reset:
	rm -rf data reports
