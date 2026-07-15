FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ADD . /app
WORKDIR /app
RUN uv sync --frozen

RUN mkdir -p /app/data
ENV DB_PATH=/app/data/pse_disclosures.db
VOLUME /app/data

# nosemgrep
CMD ["uv", "run", "-m", "src.main"]
