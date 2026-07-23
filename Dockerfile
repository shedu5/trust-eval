# Reproducible image for the trust-eval harness.
FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching. Judge SDKs are included so the container
# can do live runs; cache-only reproduction does not import them.
COPY requirements.txt requirements-judges.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-judges.txt

COPY . .
RUN pip install --no-cache-dir -e .

# Default: run the suite cache-first over the configured judges and print the
# per-class tables. With committed cache files this reproduces the report tables
# with no API key. Set TRUST_EVAL_LIVE=1 (and an API key) to fill cache misses.
CMD ["python", "-m", "trust_eval"]
