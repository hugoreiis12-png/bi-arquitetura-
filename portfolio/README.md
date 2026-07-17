# 📦 Portfolio de Projetos BI

> Camada acima do scaffolding de projeto único. Aqui mora o catálogo,
> governança transversal e biblioteca compartilhada.

## 🧭 Três padrões possíveis

| Padrão | Quando usar | Estrutura |
|---|---|---|
| **1 · Monorepo** | < 5 projetos, mesmo time, releases acoplados | Tudo num repo único, cada projeto é uma pasta |
| **2 · Template + Polyrepo** ⭐ | 5–30 projetos, times distintos, isolamento forte | Repo-template + um repo por projeto |
| **3 · Federado (Template + Shared Lib)** ⭐⭐ | > 10 projetos, padrões versionados, escala corporativa | Template + biblioteca central consumida por todos |

---

## 1. Monorepo

```
bi-portfolio/                          # 1 único repositório
├── portfolio/
│   ├── catalog/
│   │   └── projects.json
│   └── padroes/
├── vendas/
│   ├── src/
│   ├── deploy/
│   ├── scripts/
│   ├── .vscode/
│   └── README.md
├── estoque/
│   ├── src/
│   └── …
├── rh/
│   ├── src/
│   └── …
└── .github/workflows/
    └── bi-ci-cd.yml                   # matrix build: [vendas, estoque, rh]
```

✅ Prós: 1 pipeline, 1 lugar pra procurar, PRs cruzados fáceis
❌ Contras: tudo cresce junto; CI roda tudo; acesso granular difícil

---

## 2. Template + Polyrepo ⭐ recomendado

```
github.com/org/bi-template                    # TEMPLATE (este scaffolding, com tag)
github.com/org/bi-vendas                      # repo do projeto Vendas
github.com/org/bi-estoque                     # repo do projeto Estoque
github.com/org/bi-rh                          # repo do projeto RH
github.com/org/bi-portfolio-catalog           # catalog central (cross-project)
```

✅ Prós: isolamento total, CI leve, acesso granular, ciclos independentes
❌ Contras: padrões podem divergir; 1 PR de bug fix exige replicar N repos

**Como criar projeto novo:**
1. GitHub → `Use this template` → `bi-vendas`
2. Personalizar `deploy/dev/config.json`, `README.md`, `docs/data-dictionary.md`
3. Subir SP, criar workspace, primeiro deploy
4. Pronto. ~30 min, não 1 dia.

---

## 3. Federado (Template + Shared Library) ⭐⭐ escala

```
github.com/org/bi-template                    # este scaffolding como template
github.com/org/bi-shared-library              # biblioteca central
│   ├── padroes/                              # naming, revisão, modelos
│   ├── tmdl/                                 # d_calendario, _fx, utilitários
│   ├── scripts/                              # publish.ps1, refresh.ps1
│   └── ci-cd/                                # reusable workflows
github.com/org/bi-vendas                      # projeto
│   └── tools/shared-lib → submodule          # aponta pra bi-shared-library
github.com/org/bi-estoque
github.com/org/bi-rh
github.com/org/bi-portfolio-catalog           # catálogo de todos
```

✅ Prós: padrões atualizados em 1 lugar, projetos consomem via submodule, correções propagam em minutos
❌ Contras: setup inicial mais elaborado; submodule confunde devs novos

**Como projetos consomem a biblioteca:**
```bash
# Dentro do projeto:
git submodule add https://github.com/org/bi-shared-library tools/shared-lib
# Ao atualizar a lib:
git submodule update --remote --merge
# O pipeline já está configurado pra rodar os scripts do submodule
```

---

## 🎯 Recomendação

| Tamanho do time | Padrão |
|---|---|
| 1–3 devs, 1–3 projetos | **Monorepo** (mais simples) |
| 3–10 devs, 5–15 projetos | **Template + Polyrepo** ⭐ |
| > 10 devs, > 15 projetos | **Federado** ⭐⭐ |

**Hoje, faça o Template + Polyrepo.** Quando o nº de projetos passar de 15 e começar a doer replicar correção de bug em 5 repos, evolua pra Federado.

---

## 📋 Onde começar

1. Suba este scaffolding como **Template Repo** no GitHub ou Azure DevOps
2. Crie o `bi-portfolio-catalog` (este `portfolio/catalog/`)
3. Quando começar um BI novo: `Use this template` → customiza → sobe
4. Registre no catalog (PR no repo de catalog)
5. Quando doer replicar padrão, evolua pra Federado
