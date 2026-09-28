# syntax=docker/dockerfile:1

# Node is in the runtime image, not just the builder: the TypeScript task track runs
# vitest, so an image without Node could only run half the benchmark.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS builder
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM base AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
# The runtime dependencies are named rather than resolved implicitly, so what lands in the
# image is a decision in the diff. pytest is one of them: the harness grades a Python task by
# invoking `python -m pytest` in a sandbox, so an image without it can list and lint tasks but
# cannot run one -- which is exactly how CI failed before pytest moved out of the dev extra.
RUN pip install --no-cache-dir /wheels/*.whl "pydantic>=2.7" "pytest>=8" && rm -rf /wheels

COPY tasks ./tasks

# Install the vitest runtime once, at build time, into the default cache location
# (/app/.agentbench-cache) so a benchmark pass does not reach the network. Kept
# non-fatal: an image built without network access still runs the Python tasks.
RUN agentbench validate --language typescript > /dev/null 2>&1 || echo 'warning: the TypeScript runtime was not pre-installed at build time'

RUN useradd --create-home --uid 10001 bench \
    && chown -R bench:bench /app
USER bench

ENTRYPOINT ["agentbench"]
CMD ["--help"]
