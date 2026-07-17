# 📚 Biblioteca Compartilhada (bi-shared-library)

> Repositório central consumido por todos os projetos BI. Aqui mora tudo
> o que deve ser igual em todos os projetos: padrões, scripts, CI/CD,
> modelos TMDL.

## Estrutura sugerida

```
bi-shared-library/                    # repo separado, versionado em SemVer
├── padroes/
│   ├── naming-conventions.md         # MESTRE — única versão canônica
│   ├── dax-patterns.md
│   ├── power-query-patterns.md
│   ├── review-checklist.md
│   └── adr/                          # Architecture Decision Records
│       ├── 0001-pbip-em-vez-de-pbix.md
│       ├── 0002-tres-ambientes.md
│       └── README.md
├── tmdl/
│   ├── d_calendario.tmdl
│   ├── d_calendario_fiscal.tmdl
│   ├── _fx_currency_conversion.tmdl
│   ├── _util_working_days.tmdl
│   └── README.md                     # como incluir num dataset
├── scripts-ps1/
│   ├── common/
│   │   ├── auth.ps1                  # autenticação SP
│   │   ├── logging.ps1
│   │   └── config.ps1
│   ├── publish.ps1
│   ├── refresh.ps1
│   ├── extract-pbip.ps1
│   ├── compile-pbip.ps1
│   └── README.md
├── ci-cd/
│   ├── validate.yml                  # reusable workflow
│   ├── deploy-dev.yml
│   ├── promote.yml
│   └── notify-teams.yml
└── templates/
    ├── pr-template.md
    ├── issue-bug.md
    ├── issue-feature.md
    └── workspace-bootstrap.ps1       # cria workspace + SP + roles automaticamente
```

## Como um projeto consome essa biblioteca

### Opção A — Git Submodule (recomendado)

```bash
# No projeto novo, após "Use this template":
git submodule add https://github.com/org/bi-shared-library tools/shared-lib
git submodule update --init --recursive

# Para atualizar a versão consumida:
git submodule update --remote --merge
git add tools/shared-lib
git commit -m "chore: bump shared-lib to v2.2.0"
```

### Opção B — Package versionada (npm-style para PowerShell)

```powershell
# Install-Module BIStandard
Install-Module BIStandard -Scope CurrentUser -RequiredVersion 2.1.0
Import-Module BIStandard
# use as funções:
Publish-PBIDataset -DatasetPath ... -WorkspaceId ... -Environment dev
```

### Opção C — Docker image com scripts pré-instalados

```dockerfile
# Imagem custom no pipeline
FROM mcr.microsoft.com/dotnet/sdk:8.0
RUN dotnet tool install --global Microsoft.PowerBI.Tools
COPY --from=bi-shared-library:2.1.0 /scripts /opt/bi-scripts
ENV PATH="/opt/bi-scripts:${PATH}"
```

## Versionamento

- **SemVer**: `MAJOR.MINOR.PATCH`
- **MAJOR**: quebra de compatibilidade (mudou assinatura de função, schema de TMDL)
- **MINOR**: nova funcionalidade compatível (nova medida compartilhada)
- **PATCH**: bug fix, documentação

Projetos podem fixar versão (recomendado para Prod) ou seguir latest (recomendado para Dev).

## Política de contribuição

- Toda mudança na lib exige **2 revisores** (sua natureza é crítica)
- Mudanças em `padroes/` exigem aprovação do steward
- Mudanças em `tmdl/` exigem aprovação do tech-lead
- Mudanças em `scripts/` exigem aprovação do platform-team
- Mudanças em `ci-cd/` exigem aprovação do DevOps
