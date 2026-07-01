# Ludus MCP server (streamable HTTP) — a thin proxy to the backend REST API.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e ".[mcp]"

# Points at the backend service on the compose network by default.
ENV LUDUS_API_URL=http://backend:8000 \
    LUDUS_MCP_HOST=0.0.0.0 \
    LUDUS_MCP_PORT=8765

EXPOSE 8765
CMD ["ludus-mcp"]
