# Ludus backend (FastAPI + SQLModel/SQLite) reusing the ludus core.
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; SQLite ships with Python.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install the package with the [server] extra.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e ".[server]"

# Scenario/fixture/rubric assets used by scenarios (mounted or baked in).
COPY scenarios ./scenarios
COPY fixtures ./fixtures
COPY rubrics ./rubrics

# Persist SQLite + baselines in a volume.
ENV LUDUS_DATABASE_URL=sqlite:////data/ludus.db \
    LUDUS_BASELINES_DIR=/data/baselines \
    LUDUS_SCENARIOS_DIR=/app/scenarios \
    LUDUS_HOST=0.0.0.0 \
    LUDUS_PORT=8000
VOLUME ["/data"]

EXPOSE 8000
CMD ["ludus-server"]
