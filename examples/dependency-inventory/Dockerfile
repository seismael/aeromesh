# Build from the repository root, supplying a reviewed python:3.12-slim digest.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BASE_IMAGE
RUN python -c 'import os,re; assert re.fullmatch(r"[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}", os.environ["BASE_IMAGE"]), "BASE_IMAGE must be digest-pinned"'

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
WORKDIR /app
COPY constraints/ci-python.txt /app/constraints.txt
RUN python -m pip install --no-cache-dir -c /app/constraints.txt mcp==1.30.0 packaging==26.3 \
    && python -m pip check
COPY examples/dependency-inventory/server.py /app/server.py
USER 65532:65532
ENTRYPOINT ["python", "/app/server.py", "--text-input"]
