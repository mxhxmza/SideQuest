# Build from the repo root:  docker build -f backend/Dockerfile -t stop-planner-api .
# Stage 1 builds the POI DB from OSM (D2) so the image works on an ephemeral disk (D1).
FROM python:3.11-slim AS poi
WORKDIR /src
# The osmium wheel links the system libexpat.so.1, which python:*-slim no longer ships.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libexpat1 \
 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements-import.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-import.txt
COPY backend/app backend/app
COPY backend/scripts backend/scripts
# Downloads the Geofabrik extract (~250 MB) and builds data/pois.sqlite (~17 MB).
RUN python backend/scripts/import_osm.py && rm -f data/*.osm.pbf

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 POI_DB_PATH=/app/data/pois.sqlite CACHE_DB_PATH=/tmp/cache.sqlite
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app backend/app
COPY --from=poi /src/data/pois.sqlite data/pois.sqlite
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
