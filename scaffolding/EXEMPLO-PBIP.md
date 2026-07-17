# Exemplo de estrutura PBIP

> Quando você abrir o Power BI Desktop com o PBIP save mode ativado e salvar
> um arquivo `.pbip` em `src/datasets/`, o Desktop cria automaticamente a
> estrutura abaixo.

## Estrutura gerada pelo Power BI Desktop

```
src/datasets/
└── Vendas.Dataset/                  # pasta do dataset
    ├── .pbip                        # arquivo-ponte que abre no Desktop
    ├── definition/
    │   ├── version.json
    │   ├── model.tmdl               # definições do modelo semântico (TMDL)
    │   ├── relationships.tmdl       # relacionamentos
    │   ├── expressions.tmdl         # expressões (ex: parâmetros)
    │   ├── tables/
    │   │   ├── d_calendario.tmdl
    │   │   ├── d_cliente.tmdl
    │   │   ├── d_produto.tmdl
    │   │   └── f_vendas__pedido.tmdl
    │   └── cultures/                # traduções
    │       └── pt-BR.tmdl
    └── .pbi/                        # cache local (já está no .gitignore)
```

## E o Report?

Ao salvar o `.pbip`, o Power BI pergunta se você quer separar o report:

```
src/reports/
└── Vendas.Report/
    ├── .pbip
    └── definition/
        ├── version.json
        ├── report.json              # layout do relatório (JSON)
        ├── report.pbir              # ponte com o dataset
        ├── pages/
        │   ├── page-1.json
        │   ├── page-2.json
        │   └── page-3.json
        ├── visuals/
        │   └── ...
        ├── bookmarks.tmdl
        └── versionMetadata.json
```

> ✅ **Recomendado:** sempre separar dataset e report. Permite publicar
> visualmente sem tocar no modelo (e vice-versa).

## Como criar na prática

1. Power BI Desktop → `File → Save As`
2. Tipo: **Power BI Project (*.pbip)**
3. Local: `src/datasets/Vendas.Dataset/`
4. Quando perguntar "Create new Report folder?", diga **Sim** e salve em `src/reports/`
5. Volte ao VS Code — você verá os arquivos TMDL/JSON
6. `git add . && git commit -m "feat: cria dataset e report Vendas em PBIP"`
