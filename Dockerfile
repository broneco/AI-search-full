FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies (curl, unixodbc, msodbcsql18 for Azure SQL Server pyodbc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
# Cloud settings are supplied at runtime; tenant env files are excluded by .dockerignore.
COPY pyproject.toml README.md ./
COPY app ./app
COPY tenants ./tenants
COPY fixtures ./fixtures
RUN pip install --no-cache-dir .
COPY migrate_search_acl.py migrate_search_vectors.py benchmark_search.py ./
COPY migrate_model_access.py migrate_model_registry.py migrate_model_metadata.py migrate_model_limits.py ./
COPY migrate_tenant_settings.py ./
COPY verify_deployment.py ./

EXPOSE 8000

# Run FastAPI backend using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
