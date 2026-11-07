FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CASEVAULT_CONFIG=/app/config/casevault.yaml
WORKDIR /app
COPY pyproject.toml ./
COPY casevault ./casevault
COPY config ./config
RUN pip install --no-cache-dir . && useradd -r -u 10001 cv && mkdir -p /app/data && chown cv /app/data
USER cv
EXPOSE 8000
CMD ["uvicorn", "casevault.web:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
