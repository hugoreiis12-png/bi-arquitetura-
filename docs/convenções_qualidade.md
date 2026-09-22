# Convenções, revisão de qualidade e documentação

Padrões aplicáveis a modelos escritos em TMDL, o checklist de revisão e o template de
documentação do modelo.

## Índice

1. [Nomenclatura](#nomenclatura)
2. [Organização do arquivo TMDL](#organização-do-arquivo-tmdl)
3. [Checklist de revisão de modelo](#checklist-de-revisão-de-modelo)
4. [Anti-padrões de DAX e modelagem](#anti-padrões-de-dax-e-modelagem)
5. [Performance: onde olhar primeiro](#performance-onde-olhar-primeiro)
6. [Template de documentação do modelo](#template-de-documentação-do-modelo)
7. [Convenções de repositório](#convenções-de-repositório)

---

## Nomenclatura

O modelo semântico é interface de usuário. Nomes técnicos vazam para o painel de campos.

| Objeto             | Convenção                                         | Exemplo                                   |
| ------------------ | ------------------------------------------------- | ----------------------------------------- |
| Tabela de fato     | Substantivo de negócio, sem prefixo               | `Vendas`, `Estoque`                       |
| Tabela de dimensão | Substantivo singular                              | `Produto`, `Cliente`, `Calendário`        |
| Tabela técnica     | Prefixo `_` e oculta                              | `_Medidas`, `_Parâmetros`                 |
| Coluna             | Linguagem de negócio, capitalização natural       | `Preço Unitário`, `Data do Pedido`        |
| Chave              | Sufixo consistente, sempre oculta                 | `Produto SK`, `Cliente SK`                |
| Medida             | Substantivo do que mede, com unidade quando ajuda | `Faturamento`, `Ticket Médio`, `Margem %` |
| Medida auxiliar    | Prefixo `_` e oculta ou em pasta própria          | `_Base Custo`                             |
| Role               | Papel de negócio                                  | `Gerente Regional`                        |
| Grupo de cálculo   | Substantivo da dimensão de cálculo                | `Inteligência de Tempo`                   |

Decisões que devem ser tomadas uma vez e registradas no repositório:

- **Idioma dos objetos.** Português ou inglês — misturar é o pior dos dois mundos.
- **Prefixos `dim_`/`fact_`.** Úteis na camada de dados, ruins na camada semântica (o usuário
  final não deveria vê-los). Se a origem os traz, remova no modelo — é refatoração de dez
  segundos com regex no TMDL View.
- **Padrão de `displayFolder`.** Por área de negócio ou por tipo de cálculo, não os dois.
- **Onde ficam as medidas.** Tabela `_Medidas` única, ou na tabela de fato correspondente.

---

## Organização do arquivo TMDL

Ordem previsível dentro do arquivo da tabela reduz conflito de merge e acelera revisão:

```tmdl
/// Descrição da tabela.
table Vendas
    <propriedades da tabela>

    <medidas, agrupadas por displayFolder>

    <colunas, na ordem lógica de negócio>

    <hierarquias>

    <partições>

    <anotações>
```

Práticas:

- Uma linha em branco entre objetos filhos; nenhuma entre `ref`s do mesmo tipo.
- Descrição (`///`) em todo objeto visível ao usuário.
- Preservar `lineageTag` e `annotation` existentes em qualquer reescrita.
- Nunca reordenar coleções sem necessidade — gera diff de ruído.

---

## Checklist de revisão de modelo

Use antes de endossar um modelo ou aprovar um PR. Cada item é verificável.

### Estrutura

- [ ] Esquema em estrela; sem relacionamento direto entre tabelas de fato
- [ ] Cada fato tem granularidade única, declarada na descrição
- [ ] Dimensões conformadas reutilizadas, não duplicadas
- [ ] Tabela de calendário existe, é contínua e está marcada como tabela de datas
- [ ] Relacionamentos unidirecionais, salvo exceção justificada em comentário/descrição
- [ ] Nenhum relacionamento inativo órfão (sem `USERELATIONSHIP` que o use)

### Objetos e usabilidade

- [ ] Colunas técnicas e chaves com `isHidden`
- [ ] `summarizeBy: none` em todas as chaves e códigos numéricos
- [ ] `formatString` em todas as medidas visíveis
- [ ] `sortByColumn` onde a ordem alfabética não serve (meses, faixas)
- [ ] `displayFolder` coerente em medidas e colunas
- [ ] Descrição preenchida em todas as tabelas e medidas expostas
- [ ] Nenhum nome técnico da origem exposto ao usuário

### Performance

- [ ] Sem colunas de alta cardinalidade desnecessárias (IDs textuais, timestamps completos)
- [ ] Data/hora separada em data + hora quando a hora é analisada
- [ ] `isAvailableInMdx: false` em colunas de alta cardinalidade não usadas por clientes MDX
- [ ] Colunas calculadas justificadas (por que não foi feito no ETL?)
- [ ] Tipos de dados adequados: `int64` para chaves, `decimal` para valores monetários
- [ ] Modo de armazenamento coerente entre fatos e dimensões (evitar dimensão import com fato DQ
      sem `dual`)

### Governança

- [ ] RLS definida e testada com "Exibir como"
- [ ] `securityFilteringBehavior` conferido onde há bidirecional + RLS
- [ ] Parâmetros de conexão em `expressions.tmdl`, não hardcoded em cada query
- [ ] Modelo versionado como PBIP/TMDL em Git; `cache.abf` e `localSettings.json` ignorados
- [ ] `compatibilityLevel` compatível com o ambiente de destino

---

## Anti-padrões de DAX e modelagem

| Anti-padrão                                                | Sintoma                                        | Correção                                       |
| ---------------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------- |
| `LOOKUPVALUE` em medida                                    | Lento, ignora relacionamento existente         | Criar relacionamento; usar `RELATED`           |
| Coluna calculada para junção                               | Memória + refresh                              | Resolver na origem/ETL                         |
| `FILTER` sobre tabela inteira                              | Varre milhões de linhas                        | Filtrar coluna: `CALCULATE(..., 'T'[Col] = X)` |
| `IF(ISBLANK(...), 0, ...)` em toda medida                  | Materializa zeros, mata a compressão do visual | Deixar blank; tratar no visual                 |
| Medida chamando medida em 5 níveis                         | Ilegível e difícil de otimizar                 | Variáveis (`VAR`) e achatamento                |
| Bidirecional para resolver filtro pontual                  | Ambiguidade global                             | `CROSSFILTER` dentro da medida                 |
| Muitas medidas quase iguais (YTD, YoY, MTD × cada métrica) | Explosão combinatória                          | Grupo de cálculo                               |
| Formato definido no visual                                 | Inconsistência entre relatórios                | `formatString` na medida                       |
| Data como texto                                            | Sem time intelligence                          | `dataType: dateTime` + tabela de calendário    |
| Auto date/time ligado                                      | Uma tabela de datas oculta por coluna de data  | Desligar e usar calendário próprio             |

---

## Performance: onde olhar primeiro

Ordem de investigação, do mais barato ao mais caro:

1. **Cardinalidade das colunas.** VertiPaq comprime por coluna; a coluna mais cardinal domina o
   tamanho. Remova IDs de texto não usados, quebre datetime, arredonde decimais quando cabível.
2. **Colunas inúteis.** Toda coluna importada custa memória e refresh, mesmo oculta.
3. **Colunas calculadas.** Não comprimem tão bem quanto colunas importadas.
4. **Relacionamentos.** Bidirecionais e M:N ampliam o trabalho do mecanismo de fórmula.
5. **Padrão de DAX.** Iteradores sobre fatos grandes, contexto de linha desnecessário,
   `FILTER` de tabela inteira.
6. **Modo de armazenamento.** DirectQuery mal desenhado dispara consultas por visual.
7. **Agregações.** Tabelas de agregação para fatos muito grandes com consultas de alto nível.

Ferramentas: DAX Studio (Server Timings, VertiPaq Analyzer), Performance Analyzer do Desktop,
Best Practice Analyzer do Tabular Editor.

---

## Template de documentação do modelo

Use esta estrutura ao gerar documentação a partir de uma pasta TMDL. A saída de
`scripts/tmdl_audit.py` alimenta as seções factuais; a interpretação é sua.

```markdown
# Modelo semântico: <Nome>

## 1. Visão geral

Propósito de negócio, público, decisões que suporta, frequência de atualização,
nível de compatibilidade, modo de armazenamento predominante.

## 2. Arquitetura

Diagrama/descrição do esquema em estrela: fatos, dimensões, granularidades.
Origem dos dados e camadas a montante.

## 3. Tabelas

Para cada tabela: descrição, granularidade, modo de armazenamento, origem,
contagem de colunas e medidas, observações.

## 4. Medidas

Tabela com: nome, pasta, descrição, expressão DAX, formato, dependências.
Agrupar por área de negócio.

## 5. Relacionamentos

De → Para, cardinalidade, direção de filtro cruzado, ativo/inativo, justificativa
de cada bidirecional.

## 6. Segurança

Roles, expressões de RLS, OLS, como membros são atribuídos.

## 7. Atualização

Partições, políticas de refresh incremental, janela, dependências,
o que fazer quando falha.

## 8. Convenções e decisões

Padrões de nomenclatura adotados, decisões de arquitetura com trade-off,
o que foi deliberadamente deixado de fora.

## 9. Achados da auditoria

Saída do audit com priorização e plano de correção.
```

Descrições (`///`) bem escritas no TMDL fazem 80% dessa documentação se gerar sozinha. É o melhor
argumento prático para preenchê-las.

---

## Convenções de repositório

```
repo/
├── src/
│   ├── Vendas.SemanticModel/
│   │   ├── definition/            ← pasta TMDL
│   │   ├── definition.pbism
│   │   └── .pbi/                  ← parcialmente ignorado
│   └── Vendas.Report/
├── scripts/                       ← automação de deploy e auditoria
├── docs/
│   ├── dicionario-metricas.md
│   ├── matriz-barramento.md
│   └── decisoes/                  ← ADRs de arquitetura
└── .gitignore
```

`.gitignore` mínimo:

```
**/.pbi/cache.abf
**/.pbi/localSettings.json
*.pbix
```

Convenção de commit para modelos: `modelo(<tabela>): <mudança>` — ex.
`modelo(Vendas): adiciona medida Margem Líquida e oculta chaves`. Facilita rastrear qual PR
mexeu em qual objeto quando um número muda.

Registre decisões de arquitetura como ADRs curtos (contexto, decisão, consequência). Em seis
meses ninguém lembra por que aquele relacionamento é bidirecional.
