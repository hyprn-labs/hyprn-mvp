ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE} AS build
COPY deployment/locks/tools.json /build/tools.json
COPY deployment/images/install_python.py /build/install_python.py
RUN python /build/install_python.py /build/tools.json /opt/runtime
COPY deployment/locks/build-backend.json deployment/locks/engine-sources.json /build/
COPY integration/worker-requirements.lock /build/worker-requirements.lock
COPY upstream/engine-packaging /build/packaging
COPY deployment/images/build_engine.py /build/build_engine.py
RUN /opt/runtime/venv/bin/python /build/build_engine.py acquire /build
RUN /opt/runtime/uv pip install --python /opt/runtime/venv/bin/python \
    --require-hashes --only-binary=:all: --no-deps -r /build/binary.lock
RUN --network=none /opt/runtime/venv/bin/python /build/build_engine.py build /build /opt/runtime

FROM ${PYTHON_IMAGE}
RUN --network=none rm -rf /usr/local/bin/python* /usr/local/bin/pip* /usr/local/bin/idle* \
    /usr/local/bin/pydoc* /usr/local/bin/2to3* /usr/local/lib/python* /usr/local/lib/libpython* \
    /usr/local/include/python* /usr/local/lib/pkgconfig/python* /usr/local/share/man/man1/python*
COPY --from=build /opt/runtime/python /opt/runtime/python
COPY --from=build /opt/runtime/venv /opt/runtime/venv
COPY --from=build /opt/runtime/engine-build.json /opt/runtime/engine-build.json
ENV PATH=/opt/runtime/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 \
    OPENMDAO_REPORTS=0 OPENBLAS_NUM_THREADS=1
USER 65534:65534
WORKDIR /output
