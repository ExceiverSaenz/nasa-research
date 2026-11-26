# Tensile Value Review in a container: one container per reviewer, on their own computer (ADR-009).
# Build from the repository root (the build context must contain value_review/):
#   docker compose -f value_review/compose.yaml up --build
# The "test" stage runs the whole test suite on Linux; the image is not built if a test fails.

FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY value_review/requirements.txt value_review/requirements.txt
RUN pip install -r value_review/requirements.txt
COPY value_review/ value_review/

FROM base AS test
COPY value_review/requirements-dev.txt value_review/requirements-dev.txt
RUN pip install -r value_review/requirements-dev.txt \
 && python -B -m unittest discover -s value_review/tests -p "test_*.py"

FROM base AS app
# The service listens on all addresses inside the container; compose publishes it on the host's 127.0.0.1 only.
ENV VALUE_REVIEW_HOST=0.0.0.0 \
    VALUE_REVIEW_PORT=8766 \
    VALUE_REVIEW_DATA=/data \
    VALUE_REVIEW_RUN_DIR=/sources/results \
    VALUE_REVIEW_PDF_DIR=/sources/pdfs
RUN useradd --create-home --uid 1000 reviewer && mkdir -p /data /sources/results /sources/pdfs /workspace && chown -R reviewer /data
USER reviewer
EXPOSE 8766
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/api/v1/health', timeout=4)"
# Check the mounted folders (Docker Desktop creates an empty folder for a wrong path), load their papers (quick when
# nothing changed; a paper that fails is reported, not fatal), then serve. Settings can add more pairs under /sources.
CMD ["sh", "-c", "python -B -m value_review.docker_check; python -B -m value_review.ingest; exec python -B -m value_review --no-browser"]
