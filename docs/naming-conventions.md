# Convenções de Nomenclatura

> Padrão obrigatório. Última revisão: ver topo do README.

## 1. Tabelas (modelo semântico)

| Tipo | Padrão | Exemplo |
|---|---|---|
| Fato | `f_<domínio>__<granularidade>` | `f_vendas__pedido` |
| Dimensão | `d_<entidade>` | `d_cliente`, `d_produto` |
| Calendário | `d_calendario` | `d_calendario` |
| Auxiliar / helper | `_aux_<descrição>` | `_aux_metas_vendedor` |

> Use **snake_case** em nomes de tabela (o sufixo `__` diferencia de prefixo simples).

## 2. Colunas

| Tipo | Padrão | Exemplo |
|---|---|---|
| Chave primária | `<entidade>_id` | `cliente_id`, `pedido_id` |
| Chave estrangeira | `<entidade>_id` (mesmo nome) | `cliente_id` em `f_vendas__pedido` |
| Data | `dt_<evento>` | `dt_pedido`, `dt_faturamento` |
| Hora | `hr_<evento>` | `hr_inicio` |
| Valor | `<descrição>_<unidade>` | `valor_brl`, `peso_kg` |
| Booleano | `is_<condição>` / `flg_<condição>` | `is_ativo`, `flg_cancelado` |
| Texto livre | `nm_<coisa>` / `ds_<coisa>` | `nm_cliente`, `ds_status` |

> Comentário descritivo **obrigatório** em colunas calculadas.

## 3. Medidas DAX

```
<Domínio>.<Descrição> [formato]
```

- `Domínio`: agrupamento lógico (`Vendas`, `Estoque`, `RH`)
- `Descrição`: clara e curta, em PascalCase
- `[formato]`: opcional, formato de exibição

| ✅ Bom | ❌ Ruim |
|---|---|
| `Vendas.Receita Total BRL` | `M01` |
| `Vendas.Ticket Médio [R$]` | `med` |
| `Vendas.Margem %` | `calc` |
| `Estoque.Giro Dias` | `giro_dias_estoque_2024` |

### 3.1 Pasta (`displayFolder`)

Use barras (`/`) para criar hierarquia no painel de campos:

```
Vendas/Receita
Vendas/Receita Acumulada
Vendas/Margem
Vendas/Ticket
```

## 4. Colunas calculadas

Prefixo `cc_` no nome técnico + comentário descritivo. Exemplo:

```dax
// Categoria do cliente baseada no volume de compras
cc_categoria_cliente = 
VAR _vol = [Volume Compras]
RETURN
    SWITCH(
        TRUE(),
        _vol > 100000, "Ouro",
        _vol > 50000, "Prata",
        "Bronze"
    )
```

## 5. Variáveis em DAX

```dax
Receita Total BRL = 
VAR _fat = SUM('f_vendas__pedido'[valor_brl])
VAR _dev = SUM('f_vendas__pedido'[valor_devolucao_brl])
RETURN
    _fat - _dev
```

- Underscore inicial para variáveis: `_nome`
- Nomes descritivos, sem abreviações obscuras

## 6. Pastas de workspace

```
[Org] BI / [Domínio] / [Projeto]
```

Exemplo: `ACME BI / Vendas / Dashboard Comercial`

## 7. Branches Git

| Tipo | Padrão | Exemplo |
|---|---|---|
| Feature | `feat/<escopo-curto>` | `feat/calendario-fiscal` |
| Fix | `fix/<escopo-curto>` | `fix/medida-receita-duplicada` |
| Refactor | `refactor/<escopo-curto>` | `refactor/padroniza-nomes-medidas` |
| Chore | `chore/<escopo-curto>` | `chore/atualiza-gitignore` |
| Hotfix | `hotfix/<escopo-curto>` | `hotfix/refresh-prod-falhou` |

## 8. Commits (Conventional Commits)

```
<type>(<scope>): <descrição>

[body opcional]

[footer opcional com referência a work item]
```

Exemplos:
```
feat(vendas): adiciona medida de ticket médio
fix(calendario): corrige ano fiscal 2024
chore(ci): atualiza versão do pbi-tools para 1.0.0
docs(readme): adiciona seção de troubleshooting
```

## 9. Releases / Tags

```
v<MAJOR>.<MINOR>.<PATCH>  (SemVer)
```

Exemplo: `v2.4.0` — release 2, minor 4, sem correções.

Tag é criada após promoção bem-sucedida em Prod. Release notes extraídos automaticamente dos commits.
