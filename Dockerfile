# bi-architecture — imagem única p/ Portainer
# Serve: powerbi-mcp (HTTP :8000, endpoint MCP em /mcp/) + dax-staff (stdio) +
# tmdl-gateway (CLI) + pbi-tools. Workspace único via PBI_WORKSPACE_ID (env).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1

# Sistema: git/curl (repo + healthcheck) + Node 20 (dax-staff) + .NET 8 (pbi-tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates gnupg wget \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
    && wget -q https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb && rm packages-microsoft-prod.deb \
    && apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    dotnet-sdk-8.0 \
    && rm -rf /var/lib/apt/lists/*

RUN dotnet tool install --global Microsoft.PowerBI.Tools
ENV PATH="${PATH}:/root/.dotnet/tools"

WORKDIR /app

# Python: ORM + gateway + MCP server (projeto + dependências)
COPY tools/orm/pyproject.toml ./tools/orm/pyproject.toml
COPY tools/orm/README.md ./tools/orm/README.md
COPY gateway-py/pyproject.toml ./gateway-py/pyproject.toml
COPY gateway-py/README.md ./gateway-py/README.md
COPY mcp/powerbi-mcp-server/pyproject.toml ./mcp/powerbi-mcp-server/pyproject.toml
COPY mcp/powerbi-mcp-server/README.md ./mcp/powerbi-mcp-server/README.md
COPY tools/orm/src ./tools/orm/src
COPY gateway-py/src ./gateway-py/src
COPY gateway-py/tests ./gateway-py/tests
COPY mcp/powerbi-mcp-server/src ./mcp/powerbi-mcp-server/src
RUN pip install --upgrade pip \
    && pip install ./tools/orm ./gateway-py "./mcp/powerbi-mcp-server"

# TS: dax-staff (fachada MCP stdio) — build dentro da imagem
COPY package.json package-lock.json ./
RUN npm ci
COPY src_agent ./src_agent
COPY tsconfig.json ./
RUN npm run build

# Repo (PBIP src/, scripts, regras TMDL, deploy/); segredos SEMPRE via env (Portainer)
COPY src ./src
COPY scripts ./scripts
COPY deploy ./deploy
COPY tests ./tests
COPY docs ./docs

# MCP via HTTP em todas as interfaces (Portainer publica a 8000)
ENV MCP_HOST=0.0.0.0 MCP_PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import socket;socket.create_connection(('127.0.0.1',8000),timeout=5)"

CMD ["powerbi-mcp", "--http"]
