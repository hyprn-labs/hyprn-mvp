FROM python:3.12.11-slim-bookworm
COPY wheels /wheels
COPY application/requirements.lock /requirements.lock
RUN python -m pip install --no-index --find-links=/wheels --require-hashes -r /requirements.lock && rm -rf /wheels
COPY application /app/application
COPY contracts /app/contracts
COPY ui-dist /app/ui
ENV PYTHONPATH=/app/application/src PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
USER 10002:10002
CMD ["python","-m","uvicorn","hyprn_mvp_app.api:from_environment","--factory","--host","0.0.0.0","--port","8000","--no-access-log"]
