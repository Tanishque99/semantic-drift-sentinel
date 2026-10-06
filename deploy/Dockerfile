# Cloud Run image for the async semantic-evaluation adapter.
# Mirrors layer 2 of the architecture. Local `make demo` does not need this;
# it is here so the same code deploys to real Cloud Run unchanged.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY pyproject.toml requirements.txt ./
RUN pip install -e ".[serve]" || pip install -r requirements.txt fastapi uvicorn

COPY src ./src
RUN pip install -e .

# Cloud Run provides $PORT.
ENV PORT=8080
CMD exec uvicorn --factory sentinel.adapter:build_app --host 0.0.0.0 --port ${PORT}
