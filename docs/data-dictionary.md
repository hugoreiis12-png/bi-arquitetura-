# Dicionário de Dados

> Catálogo vivo de tabelas, colunas e medidas do projeto.
> Toda nova tabela/medida **deve** ser registrada aqui no mesmo PR.

---

## 1. Modelo: `Vendas`

**Descrição:** Modelo semântico de vendas B2B.
**Workspace:** `ACME BI / Vendas / Modelo Vendas`
**Owner:** Steward de Vendas
**Atualizado em:** _automático via CI_

### 1.1 Tabelas

#### `d_calendario`
- **Tipo:** Dimensão
- **Granularidade:** 1 linha por dia
- **Origem:** `_calendario.tmdl` (em `src/shared/`)
- **Range:** 2018-01-01 a 2030-12-31

| Coluna | Tipo | Descrição |
|---|---|---|
| `date` | Data | Data completa |
| `ano` | Inteiro | Ano (YYYY) |
| `mes` | Inteiro | Mês (1-12) |
| `mes_nome` | Texto | Nome do mês em PT-BR |
| `trimestre` | Inteiro | Trimestre (1-4) |
| `semestre` | Inteiro | Semestre (1-2) |
| `ano_mes` | Texto | YYYY-MM (ordenação) |
| `dt_fiscal_ano_inicio` | Data | Início do ano fiscal (01/04/AAAA) |
| `flg_feriado` | Booleano | É feriado nacional? |
| `flg_fim_de_semana` | Booleano | Sábado ou domingo? |

#### `d_cliente`
- **Tipo:** Dimensão
- **Granularidade:** 1 linha por cliente
- **Origem:** CRM (tabela `customers`)

| Coluna | Tipo | Descrição |
|---|---|---|
| `cliente_id` | Inteiro | PK do CRM |
| `nm_cliente` | Texto | Razão social |
| `cnpj` | Texto | CNPJ (apenas dígitos) |
| `segmento` | Texto | PME, Enterprise, Governo |
| `is_ativo` | Booleano | Cliente ativo? |
| `dt_cadastro` | Data | Data de cadastro |

#### `d_produto`
- **Tipo:** Dimensão
- **Granularidade:** 1 linha por SKU

| Coluna | Tipo | Descrição |
|---|---|---|
| `produto_id` | Inteiro | PK do ERP |
| `sku` | Texto | SKU comercial |
| `nm_produto` | Texto | Descrição |
| `categoria` | Texto | Categoria comercial |
| `linha` | Texto | Linha de produto |

#### `f_vendas__pedido`
- **Tipo:** Fato
- **Granularidade:** 1 linha por pedido
- **Origem:** ERP (tabela `sales_orders`)

| Coluna | Tipo | Descrição |
|---|---|---|
| `pedido_id` | Inteiro | PK do pedido |
| `cliente_id` | Inteiro | FK → `d_cliente` |
| `produto_id` | Inteiro | FK → `d_produto` |
| `dt_pedido` | Data | FK → `d_calendario` |
| `dt_faturamento` | Data | Data do faturamento |
| `valor_brl` | Decimal | Valor bruto (BRL) |
| `valor_desconto_brl` | Decimal | Desconto aplicado |
| `valor_devolucao_brl` | Decimal | Valor devolvido |
| `quantidade` | Inteiro | Quantidade de itens |
| `cc_categoria_cliente` | Texto | Categoria calculada (Bronze/Prata/Ouro) |

### 1.2 Medidas

| Medida | Pasta | Descrição | Fórmula resumida |
|---|---|---|---|
| `Vendas.Receita Total BRL` | Vendas/Receita | Receita líquida após devoluções | `SUM(fat) - SUM(dev)` |
| `Vendas.Receita Bruta BRL` | Vendas/Receita | Receita antes de deduções | `SUM(fat)` |
| `Vendas.Receita Acumulada BRL` | Vendas/Receita | Receita YTD | `TOTALYTD([Receita Total])` |
| `Vendas.Margem %` | Vendas/Margem | Margem percentual | `DIVIDE([Lucro], [Receita])` |
| `Vendas.Ticket Médio [R$]` | Vendas | Valor médio por pedido | `DIVIDE([Receita], DISTINCTCOUNT([pedido_id]))` |
| `Vendas.Pedidos` | Vendas | Quantidade de pedidos | `DISTINCTCOUNT([pedido_id])` |
| `Vendas.Clientes Únicos` | Vendas | Quantidade de clientes com venda | `CALCULATE(DISTINCTCOUNT([cliente_id]), [Receita] > 0)` |
| `Vendas.Estoque.Giro Dias` | Vendas/Estoque | Dias de cobertura do estoque | `DIVIDE([Estoque Valor], [CMV]) * 30` |

### 1.3 Roles (RLS)

| Role | Filtro | Usuários / Grupos |
|---|---|---|
| `Gerente Regional` | `d_cliente[regiao] = USERPRINCIPALNAME()` | Grupo AD `BI-Gerentes-Regionais` |
| `Vendedor` | `d_cliente[vendedor_email] = USERPRINCIPALNAME()` | Grupo AD `BI-Vendedores` |
| `Auditor` | (sem filtro) | Equipe de auditoria interna |

---

## 2. Próximos modelos a catalogar

- `Estoque` (a fazer)
- `Financeiro` (a fazer)
- `RH` (a fazer)

---

**Mantenha este arquivo atualizado a cada PR que altere o modelo.**
