.PHONY: install demo jev serve test clean

PY ?= python3

install:   ## install deps (includes the Jev SDK)
	$(PY) -m pip install -e .

demo:      ## run the full end-to-end loop (needs TYPESAFE_API_KEY)
	$(PY) -m sentinel

jev:       ## run the Jev backend explicitly (needs TYPESAFE_API_KEY)
	JEV_BACKEND=jev $(PY) -m sentinel

serve:     ## run the Cloud Run async adapter locally (needs fastapi+uvicorn)
	$(PY) -m uvicorn --factory sentinel.adapter:build_app --port 8080

test:      ## run the test suite
	$(PY) -m pytest -q

clean:
	rm -rf data/*.duckdb __pycache__ .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
