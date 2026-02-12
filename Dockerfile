FROM python:3.13-slim
WORKDIR /app

COPY requirements.txt .
# Install build deps for psutil (no wheel for python3.13+aarch64), then remove after pip install
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpython3.13-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc libpython3.13-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" myuser

COPY . .
# So myuser can write to cache DB, sessions DB, and any runtime files
RUN chown -R myuser:myuser /app

USER myuser
ENV PATH="/home/myuser/.local/bin:$PATH"

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port $PORT"]
