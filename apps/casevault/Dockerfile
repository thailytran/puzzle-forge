FROM python:3.12-slim
ARG VERSION=dev
ARG GIT_SHA=
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CASEVAULT_CONFIG=/app/config/casevault.yaml \
    CASEVAULT_GIT_SHA=${GIT_SHA}
LABEL org.opencontainers.image.title="casevault" org.opencontainers.image.version="${VERSION}"
WORKDIR /app
COPY pyproject.toml ./
COPY casevault ./casevault
COPY config ./config
RUN pip install --no-cache-dir . && useradd -r -u 10001 cv && mkdir -p /app/data && chown cv /app/data
USER cv
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["sh", "-c", "python -m casevault migrate && exec uvicorn casevault.web:app_factory --factory --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' --no-server-header"]
