# Reproducible environment for EquiCVD Bench.
#   docker build -t equicvd .
#   docker run --rm -v "$PWD/data:/app/data" -v "$PWD/outputs:/app/outputs" equicvd
FROM python:3.12.6-slim

WORKDIR /app
COPY requirements-lock.txt .
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY pyproject.toml README.md LICENSE ./
COPY equicvd ./equicvd
COPY tests ./tests
RUN pip install --no-cache-dir --no-deps -e . && pytest -q

COPY scripts/reproduce.sh ./scripts/reproduce.sh
CMD ["bash", "scripts/reproduce.sh"]
