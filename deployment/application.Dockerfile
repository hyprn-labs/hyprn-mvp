ARG PYTHON_IMAGE
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS ui
WORKDIR /build/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY ui ./
RUN --network=none npm run build

FROM ${PYTHON_IMAGE} AS python
COPY deployment/locks/tools.json /build/tools.json
COPY deployment/images/install_python.py /build/install_python.py
RUN python /build/install_python.py /build/tools.json /opt/runtime
COPY application/requirements.lock /build/requirements.lock
RUN /opt/runtime/uv pip install --python /opt/runtime/venv/bin/python \
    --require-hashes --only-binary=:all: --no-deps -r /build/requirements.lock

FROM ${PYTHON_IMAGE} AS local
RUN --network=none rm -rf /usr/local/bin/python* /usr/local/bin/pip* /usr/local/bin/idle* \
    /usr/local/bin/pydoc* /usr/local/bin/2to3* /usr/local/lib/python* /usr/local/lib/libpython* \
    /usr/local/include/python* /usr/local/lib/pkgconfig/python* /usr/local/share/man/man1/python*
COPY --from=python /opt/runtime/python /opt/runtime/python
COPY --from=python /opt/runtime/venv /opt/runtime/venv
COPY application /app/application
COPY contracts /app/contracts
COPY --from=ui /build/ui/dist /app/ui
ENV PATH=/opt/runtime/venv/bin:$PATH PYTHONPATH=/app/application/src PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER 10002:10002
CMD ["python","-m","uvicorn","hyprn_mvp_app.api:from_environment","--factory","--host","0.0.0.0","--port","8000","--no-access-log"]

FROM python AS cloud-python
COPY editions/cloud/requirements.lock /build/cloud-requirements.lock
RUN /opt/runtime/uv pip install --python /opt/runtime/venv/bin/python \
    --require-hashes --only-binary=:all: --no-deps -r /build/cloud-requirements.lock

FROM local AS cloud
COPY --from=cloud-python /opt/runtime/venv /opt/runtime/venv
COPY editions/cloud/src /app/editions/cloud/src
COPY deployment/managed_assistant.py deployment/managed_skill.py /app/deployment/
COPY docs/agents/scientific-engineering /app/docs/agents/scientific-engineering
ENV PYTHONPATH=/app/application/src:/app/editions/cloud/src:/app/deployment
CMD ["python","-m","uvicorn","hyprn_mvp_cloud.asgi:from_environment","--factory","--host","0.0.0.0","--port","8000","--no-access-log"]
