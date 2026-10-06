.PHONY: install demo claude jev serve test clean

PY ?= python3

install:   ## install core deps (mock backend works with just these)
	$(PY) -m pip install -e .

demo:      ## run the full end-to-end loop (auto-selects backend)
	$(PY) -m sentinel

claude:    ## force the Claude-backed judge (needs ANTHROPIC_API_KEY)
	JEV_BACKEND=claude $(PY) -m sentinel

jev:       ## force the real Jev backend (needs TYPESAFE_API_KEY + typesafe-sdk)
	JEV_BACKEND=jev $(PY) -m sentinel

serve:     ## run the Cloud Run async adapter locally (needs fastapi+uvicorn)
	$(PY) -m uvicorn --factory sentinel.adapter:build_app --port 8080

test:      ## run the test suite
	$(PY) -m pytest -q

clean:
	rm -rf data/*.duckdb __pycache__ .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
