# tmdl-gateway — Gateway Python separado (só-TMDL)

Módulo separado do `dax-staff-mcp` (fachada TS). Todo versionamento entra e sai
como pasta TMDL (`definition/`). Sem PBIX, sem escrita direta via XMLA no caminho
de versionamento.

## Fluxos

- `pull-para-IDE`: `pull_propose` (somente leitura + `tmdl_audit`) → usuário aceita
  (`accept:true`) → `pull_apply` (único ponto que sobrescreve `definition/`).
- `commit`: exige approval token single-use (15min; `main`/`Vendas` = 2 aprovadores).
  Ordem: valida token → `audit --fail_on_high` → lint Conventional Commits →
  `branch → dataset` → git commit (+ PR opcional).
- `DAX RUN` local: auto-detecta `localhost:<porta>` via sidecar
  (`ListLocalInstances`), valida+audit+compila, escreve no modelo em memória em
  transação e persiste `definition/` + `ClearCache` + smoke `EVALUATE`.
- Bulk: sempre em transação (`Begin` → chunks de 50 → `Commit`/`Rollback`).

## Layout

```
gateway-py/src/tmdl_gateway/
  branching.py   # branch -> dataset (espelha Settings TS/py)
  proposals.py   # store de proposal_id (arquivo JSON, TTL 30min)
  approvals.py   # tokens single-use (arquivo JSON, TTL 15min)
  sidecar.py     # cliente do binário powerbi-modeling-mcp lado-a-lado
  gateway.py     # orquestração pull/commit/dax-run/bulk
  cli.py         # CLI chamada pela fachada TS (JSON no stdout)
```

## Uso (via fachada TS ou direto)

```bash
py -m tmdl_gateway.cli pull-propose --workspace "[DEV] Vendas" --dataset Vendas_Dev
py -m tmdl_gateway.cli pull-apply --proposal <id> --accept
py -m tmdl_gateway.cli approval-request --action tmdl_commit --target "feat/x:Vendas_preview_x"
py -m tmdl_gateway.cli commit --branch feat/x --message "feat(vendas): ..." --approval <token>
py -m tmdl_gateway.cli dax-run --dataset-path src/datasets/Vendas.Dataset
```
