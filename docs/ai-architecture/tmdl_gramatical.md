# TMDL — gramática da linguagem

Referência de sintaxe. Consulte antes de escrever TMDL, e especialmente antes de afirmar que
algo é ou não válido.

## Índice

1. [O que TMDL é](#o-que-tmdl-é)
2. [Estrutura de pasta](#estrutura-de-pasta)
3. [Declaração de objeto](#declaração-de-objeto)
4. [Propriedades](#propriedades)
5. [Propriedades padrão e expressões](#propriedades-padrão-e-expressões)
6. [Descrições](#descrições)
7. [Referências entre objetos e a palavra-chave `ref`](#referências-entre-objetos-e-a-palavra-chave-ref)
8. [Declaração parcial](#declaração-parcial)
9. [Indentação, espaços e caixa](#indentação-espaços-e-caixa)
10. [Erros comuns e como reconhecê-los](#erros-comuns-e-como-reconhecê-los)

---

## O que TMDL é

Sintaxe textual de definição para modelos tabulares em nível de compatibilidade 1200 ou superior
(SQL Server Analysis Services 2016+, Azure Analysis Services, Fabric / Power BI Premium).

Quatro propriedades que explicam todas as decisões de design da linguagem:

- **Paridade total com o TOM** (Tabular Object Model). Cada objeto TMDL expõe exatamente as
  mesmas propriedades da classe TOM correspondente. Se existe no TOM, existe no TMDL — e o
  contrário também: se você não acha a propriedade no TOM, ela não existe no TMDL.
- **Legível por humano**, gramática no espírito do YAML: delimitadores mínimos, indentação
  marcando relação pai-filho.
- **Boa para expressões embutidas** de linguagens diferentes (DAX, M) dentro do mesmo documento.
- **Boa para controle de versão**: um arquivo por objeto de primeiro nível produz diffs legíveis
  e conflitos de merge tratáveis, ao contrário do JSON monolítico do TMSL (`model.bim`).

Exemplo compacto de modelo completo:

```tmdl
database Sales
    compatibilityLevel: 1567

model Model
    culture: en-US

table Sales

    partition 'Sales-Partition' = m
        mode: import
        source =
            let
                Source = Sql.Database(Server, Database)
            in
                Source

    measure 'Sales Amount' = SUMX('Sales', 'Sales'[Quantity] * 'Sales'[Net Price])
        formatString: $ #,##0

    column 'Product Key'
        dataType: int64
        isHidden
        sourceColumn: ProductKey
        summarizeBy: none

relationship cdb6e6a9-c9d1-42b9-b9e0-484a1bc7e123
    fromColumn: Sales.'Product Key'
    toColumn: Product.'Product Key'

role Role_Store1
    modelPermission: read
    tablePermission Store = 'Store'[Store Code] IN {1,10,20,30}

expression Server = "localhost" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]
```

---

## Estrutura de pasta

Um nível de subpastas, todas com arquivos `.tmdl`:

```
definition/
├── cultures/
│   ├── en-US.tmdl
│   └── pt-BR.tmdl
├── perspectives/
│   └── perspective1.tmdl
├── roles/
│   ├── role1.tmdl
│   └── role2.tmdl
├── tables/
│   ├── Calendar.tmdl
│   ├── Customer.tmdl
│   ├── Product.tmdl
│   └── Sales.tmdl
├── relationships.tmdl
├── functions.tmdl
├── expressions.tmdl
├── dataSources.tmdl
├── model.tmdl
└── database.tmdl
```

Regras de granularidade — decorar isto evita procurar arquivo que não existe:

| Escopo                | Granularidade                                                              |
| --------------------- | -------------------------------------------------------------------------- |
| `database.tmdl`       | um arquivo, definição do banco (inclui `compatibilityLevel`)               |
| `model.tmdl`          | um arquivo, propriedades do modelo + `ref` de todas as coleções            |
| `dataSources.tmdl`    | **todas** as fontes de dados num arquivo                                   |
| `expressions.tmdl`    | **todas** as expressões compartilhadas (parâmetros M, queries) num arquivo |
| `functions.tmdl`      | **todas** as funções definidas pelo usuário (UDF DAX) num arquivo          |
| `relationships.tmdl`  | **todos** os relacionamentos num arquivo                                   |
| `cultures/*.tmdl`     | um arquivo **por** cultura                                                 |
| `perspectives/*.tmdl` | um arquivo **por** perspectiva                                             |
| `roles/*.tmdl`        | um arquivo **por** role                                                    |
| `tables/*.tmdl`       | um arquivo **por** tabela                                                  |

**Tudo que é filho de tabela mora no arquivo da tabela**: colunas, medidas, hierarquias,
partições, `calculationGroup`, `detailRowsDefinition`, anotações da tabela. Não procure
`measures/` — não existe por padrão.

---

## Declaração de objeto

Tipo do objeto TOM seguido do nome. Toda a árvore TOM a partir de `Database` está exposta
(exceto o objeto `Server`).

```tmdl
model Model
    culture: en-US

table Sales

    measure Sales = SUM('Sales'[Amount])
        formatString: $ #,##0

    column 'Customer Key'
        dataType: int64
        sourceColumn: CustomerKey
```

### Quando o nome precisa de aspas simples

Se contiver qualquer um destes caracteres: ponto (`.`), igual (`=`), dois-pontos (`:`),
aspa simples (`'`), ou espaço em branco.

```tmdl
table 'Fato Vendas'
    column 'Valor Líquido'
    measure 'Margem %'
```

Aspa simples dentro do nome é escapada dobrando:

```tmdl
column 'Client''s Name'
```

### Coleções filhas são implícitas

Não se declara coleção. Todo `column` no escopo de uma `table` entra em `table.Columns`.
Os filhos **não precisam ser contíguos nem ordenados** — colunas e medidas podem se intercalar
livremente. (Ainda assim, agrupe por tipo: legibilidade e diffs agradecem.)

---

## Propriedades

Vêm depois da declaração do objeto, com dois-pontos, valor na **mesma linha**:

```tmdl
table Sales
    lineageTag: e9374b9a-faee-4f9e-b2e7-d9aafb9d6a91

    column Quantity
        dataType: int64
        isHidden
        isAvailableInMdx: false
        sourceColumn: Quantity
        summarizeBy: sum
        displayFolder: "Métricas ""Base"""
```

Regras:

- Valor **nunca** é multilinha (para multilinha use expressão, com `=`).
- Texto: aspas duplas são opcionais e removidas na serialização. **Obrigatórias** quando o valor
  tem espaço à esquerda ou à direita. Aspas duplas internas escapam dobrando (`""`).
- Booleanos: forma longa (`isHidden: true`) ou atalho — só o nome da propriedade implica `true`.
  Não existe atalho para `false`; escreva `isHidden: false`.
- Enumerações usam camelCase na escrita (`summarizeBy: none`, `mode: import`), mas a leitura é
  case-insensitive.

### Referências nomeadas dentro de propriedades

Algumas propriedades apontam para outros objetos do modelo e seguem as mesmas regras de aspas:

```tmdl
table Product

    column Category
        sortByColumn: 'Category Order'

    hierarchy 'Product Hierarchy'
        level Category
            column: Category

perspective Product
    perspectiveTable Product
        perspectiveMeasure '# Products'
```

Qualificação total usa notação de ponto: `'Table 1'.'Column 1'`.

---

## Propriedades padrão e expressões

Alguns tipos têm uma **propriedade padrão** atribuída depois do `=`, na mesma linha ou como
bloco multilinha na linha seguinte.

```tmdl
table Sales

    measure 'Sales Amount' = SUM('Sales'[Amount])
        formatString: $ #,##0

    measure Quantity =
            var result = SUMX('Sales', 'Sales'[Qty])
            return result
        formatString: #,##0

    partition Sales-Partition1 = m
        mode: import
        source =
            let
                Source = Sql.Database(Server, Database)
            in
                Source
```

### Regras de expressão multilinha

- Fica na linha **imediatamente** após a declaração do objeto ou da propriedade.
- Indentada **um nível mais fundo** que as propriedades do objeto pai; todo o corpo dentro desse nível.
- Espaço em branco de indentação externa além do nível do pai é removido.
- Linhas verticalmente vazias (sem espaços) são preservadas como parte da expressão.
- Linhas em branco e espaços à direita, no fim, são descartados.

### Delimitador de três crases

Use quando precisar preservar indentação exata, linhas em branco com espaços, ou espaço à direita.
O delimitador vai logo após o `=`, e a linha final do delimitador define a margem esquerda.

````tmdl
table Table1

    measure Measure1 = ```
                var myVar = TODAY()
                return myVar
            ```
````

O serializador aplica crases automaticamente quando detecta conteúdo que se perderia num
round-trip. Na maioria dos casos, indentação correta basta — não polua o arquivo com crases.

### Propriedades tratadas como expressão

| Objeto                     | Propriedade                                         | Linguagem    |
| -------------------------- | --------------------------------------------------- | ------------ |
| Measure                    | Expression                                          | DAX          |
| Function (UDF)             | Expression                                          | DAX          |
| CalculatedColumn           | Expression                                          | DAX          |
| CalculationItem            | Expression                                          | DAX          |
| CalculationGroupExpression | Expression                                          | DAX          |
| FormatStringDefinition     | Expression                                          | DAX          |
| DetailRowsDefinition       | Expression                                          | DAX          |
| DataCoverageDefinition     | Expression                                          | DAX          |
| TablePermission            | FilterExpression                                    | DAX          |
| KPI                        | StatusExpression, TargetExpression, TrendExpression | DAX          |
| MPartitionSource           | Expression                                          | M            |
| NamedExpression            | Expression                                          | M            |
| CalculatedPartitionSource  | Expression                                          | DAX          |
| QueryPartitionSource       | Query                                               | query nativa |
| BasicRefreshPolicy         | SourceExpression, PollingExpression                 | M            |
| LinguisticMetadata         | Content                                             | XML ou JSON  |
| JsonExtendedProperty       | Value                                               | JSON         |

### Propriedade padrão por tipo (as mais usadas)

| Objeto                                       | Propriedade padrão | Linguagem                  |
| -------------------------------------------- | ------------------ | -------------------------- |
| Measure / CalculatedColumn / CalculationItem | Expression         | DAX                        |
| TablePermission                              | FilterExpression   | DAX                        |
| ColumnPermission                             | MetadataPermission | enum `MetadataPermission`  |
| NamedExpression / MPartitionSource           | Expression         | M                          |
| Partition                                    | SourceType         | enum `PartitionSourceType` |
| DataSource                                   | Type               | enum `DataSourceType`      |
| Annotation / StringExtendedProperty          | Value              | texto                      |
| JsonExtendedProperty                         | Value              | JSON                       |
| LinguisticMetadata                           | Content            | JSON                       |

---

## Descrições

Cidadão de primeira classe, com sintaxe própria: barra tripla acima da declaração,
**sem linha em branco** entre o bloco de descrição e o token do tipo do objeto.

```tmdl
/// Fatos de venda com granularidade de item de pedido.
table Sales

    /// Receita bruta, sem descontos comerciais.
    /// Não usar para análise de margem — ver [Margem Líquida].
    measure 'Sales Amount' = SUM('Sales'[Amount])
        formatString: #,##0
```

O serializador quebra descrições longas em várias linhas para manter o documento abaixo do
comprimento máximo (padrão 80 caracteres). Descrever cada objeto é a prática recomendada e é a
matéria-prima de qualquer documentação automatizada do modelo.

---

## Referências entre objetos e a palavra-chave `ref`

`ref` tem dois usos.

**1. Escopo sem redefinir.** Referenciar um objeto existente para adicionar filhos a ele:

```tmdl
createOrReplace

    ref table Sales
        measure '# Products (with Sales)' = DISTINCTCOUNT('Sales'[ProductKey])
            formatString: #,##0
```

Isso adiciona/substitui a medida sem tocar no resto da tabela `Sales`.

**2. Ordenação determinística de coleção.** No arquivo do objeto pai, `ref` fixa a ordem dos
itens da coleção do TOM. É isto que evita diffs espúrios no Git em objetos serializados em
arquivos separados (tabelas, roles, cultures, perspectivas):

```tmdl
model Model

ref table Calendar
ref table Sales
ref table Product

ref culture pt-BR

ref role 'Stores Cluster 1'
```

Comportamento:

- **Desserialização**: `ref` sem arquivo correspondente é ignorado; arquivo sem `ref` é
  acrescentado ao **fim** da coleção.
- **Serialização**: todos os objetos de coleção recebem `ref`; coleção com um único item **não**
  emite `ref`; não há linha em branco entre `ref`s do mesmo tipo.

---

## Declaração parcial

A definição de um objeto pode ser dividida entre arquivos, como classes parciais em C#.
Você pode, por exemplo, manter todas as medidas de todas as tabelas num único `measures.tmdl`:

```tmdl
table Sales

    measure 'Sales Amount' = SUM('Sales'[Amount])
        formatString: $ #,##0

table Product

    measure CountOfProduct = COUNTROWS('Product')
```

**Restrição:** a mesma propriedade não pode ser declarada duas vezes. Duas medidas de mesmo nome
para a mesma tabela em documentos diferentes = erro de parsing.

Isto é possível, mas não é o layout padrão emitido pelo serializador. Se adotar, documente a
convenção no repositório — quem abrir a pasta esperando medidas dentro do arquivo da tabela vai
concluir que elas sumiram.

---

## Indentação, espaços e caixa

Três níveis de indentação por objeto:

- Nível 1 — declaração do objeto
- Nível 2 — propriedades do objeto
- Nível 3 — expressões multilinha das propriedades

O padrão do serializador é **uma tabulação por nível**. Nunca misture tab e espaço no mesmo
documento — é a causa silenciosa de metade dos `TmdlFormatException`.

Indenta-se:

- entre cabeçalho de seção e propriedades (`table` → `isHidden`);
- entre objeto e filhos (`table` → `measure`);
- entre objeto e sua expressão multilinha (`table` → `measure` → corpo DAX).

**Não** precisam de indentação, por serem implicitamente aninhados na raiz `database`/`model`:
`model`, tabelas, expressões compartilhadas, roles, cultures, perspectivas, relacionamentos,
dataSources, queryGroups, anotações e propriedades estendidas de nível de modelo.

Espaços em branco (fora de crases e aspas duplas):

- valores de propriedade têm espaço à esquerda/direita cortado;
- linhas de espaço no fim de expressões são descartadas;
- linhas só com espaços/tabs viram linhas vazias.

Caixa: a API escreve em **camelCase** (tipos de objeto, palavras-chave, valores de enum) e lê
sem diferenciar maiúsculas de minúsculas.

---

## Erros comuns e como reconhecê-los

| Sintoma                               | Causa provável                                                                                                                    |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `TmdlFormatException` com nº de linha | Sintaxe: indentação inconsistente, palavra-chave inválida, `:` onde devia ser `=`                                                 |
| `TmdlSerializationException`          | Sintaxe válida, semântica TOM inválida: tipo de valor errado, propriedade inexistente naquele objeto, referência a objeto ausente |
| Script recusado no TMDL View          | Falta o comando `createOrReplace` no topo, ou há mais de um verbo de comando                                                      |
| Arquivo de pasta recusado             | Tem comando (`createOrReplace`) — arquivos de pasta não levam comando                                                             |
| Medida "some" ao aplicar              | `createOrReplace` de `table X` sem `ref` substitui a tabela inteira, apagando o que não estava no script                          |
| Diff gigante no Git sem mudança real  | Ordenação de coleção perdida — faltam `ref`s no arquivo pai, ou serializador de versão diferente                                  |
| Propriedade rejeitada no apply        | Nível de compatibilidade abaixo do exigido pela propriedade                                                                       |
| Visual quebrado após rename           | Renomear campo não atualiza referências no relatório                                                                              |

O `TmdlFormatException` traz `Document`, `Line` e `LineText` — sempre peça/leia esses três antes
de tentar adivinhar o erro.
