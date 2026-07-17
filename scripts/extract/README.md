# Extract script

## Quick start

```bash
# Install dependencies
pip install httpx msal pyyaml structlog

# Set credentials
export PBI_TENANT_ID="your-tenant"
export PBI_SP_CLIENT_ID="your-sp-client-id"
export PBI_SP_CLIENT_SECRET="your-sp-secret"

# Run
python extract_from_powerbi.py \
  --workspace "bi-vendas-prod" \
  --dataset "Vendas.Dataset" \
  --output ./src/datasets \
  --include-reports \
  --generate-docs \
  --git-commit
```

## What it does

1. Authenticates with Service Principal
2. Lists datasets in the workspace
3. Picks the target dataset (first by default, or by name/ID)
4. Extracts TMDL files via `pbi-tools extract`
5. Generates:
   - `overview.yaml` (machine-readable summary)
   - `README.md` (human overview)
   - `docs/data-dictionary.md` (catalog of tables/measures)
6. Optionally creates git commit
7. Prints summary with file count and next steps

## Output structure

```
src/datasets/Vendas.Dataset/
├── .pbip                              # from pbi-tools
├── README.md                          # generated
├── overview.yaml                      # generated
├── definition/
│   ├── version.json
│   ├── model.tmdl
│   ├── relationships.tmdl
│   ├── tables/
│   │   ├── d_calendario.tmdl
│   │   └── ...
│   └── roles/
│       └── ...
├── dataSources/
│   └── ...
└── docs/
    └── data-dictionary.md             # generated
```

## Prerequisites

- Python 3.11+
- `pbi-tools` CLI (`dotnet tool install --global Microsoft.PowerBI.Tools`)
- Service Principal with permissions on the workspace
- Premium/PPU/Fabric capacity (for XMLA endpoint)
- Git configured
