# Derive from the reviewed numerical dependency image without installing packages.
# The manager verifies its immutable identity and retained complete hash lock.
ARG ENGINE_IMAGE
FROM ${ENGINE_IMAGE}
ARG WORKER_SHA256
ARG RESULTS_SHA256
LABEL org.hyprn-mvp.worker_sha256=${WORKER_SHA256}
LABEL org.hyprn-mvp.results_sha256=${RESULTS_SHA256}
USER 0:0
COPY worker.py /opt/hyprn_mvp_integration/worker.py
COPY results.py /opt/hyprn_mvp_integration/results.py
COPY exploration.py /opt/hyprn_mvp_integration/exploration.py
COPY surrogate.py /opt/hyprn_mvp_integration/surrogate.py
COPY __init__.py /opt/hyprn_mvp_integration/__init__.py
# Precompile trusted runtime libraries without importing candidate code. Hash-based
# bytecode stays inside the immutable image; every run still gets a fresh container.
# The build manager applies --network=none to every RUN in this image.
RUN python -m compileall -q --invalidation-mode checked-hash \
    /opt/runtime/venv/lib/python3.12/site-packages /opt/hyprn_mvp_integration
ENV PYTHONPATH=/opt PYTHONDONTWRITEBYTECODE=1 OPENMDAO_REPORTS=0 OPENBLAS_NUM_THREADS=1
USER 65534:65534
WORKDIR /output
