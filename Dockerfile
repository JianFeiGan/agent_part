FROM python:3.11-slim

WORKDIR /app

# Install uv and build dependencies (needed for compiling C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Copy dependency files (README.md needed by pyproject.toml build)
COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "python", "main.py"]