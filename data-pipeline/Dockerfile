FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN pip install --no-cache-dir "uv==0.12.5"

WORKDIR /app

# Dependencies change less often than source code, so install them in their own layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin pipeline
USER 10001

ENV PATH="/opt/venv/bin:${PATH}"
ENTRYPOINT ["retail-pipeline"]
