# Arquitetura de BI & Analytics

Para quando o pedido é de desenho, não de código: o que deve existir, em que camada, sob qual
governança, e como chegar lá. TMDL entra no fim dessa cadeia — é a materialização da camada
semântica.

## Índice

1. [Levantamento de requisitos](#levantamento-de-requisitos)
2. [Camadas de dados](#camadas-de-dados)
3. [Modelagem dimensional](#modelagem-dimensional)
4. [A camada semântica](#a-camada-semântica)
5. [TOGAF: capacidade de BI & Analytics](#togaf-capacidade-de-bi--analytics)
6. [Governança e gestão de metadados](#governança-e-gestão-de-metadados)
7. [Segurança](#segurança)
8. [Roadmap e maturidade](#roadmap-e-maturidade)
9. [Anti-padrões de arquitetura](#anti-padrões-de-arquitetura)

---

## Levantamento de requisitos

A causa mais comum de projeto de BI fracassado não é técnica. É entregar o dashboard que foi
pedido em vez do que resolve a decisão.

**Comece pela decisão, não pelo indicador.** Sequência que funciona:

1. **Decisão** — que escolha alguém vai fazer diferente por causa deste dado?
2. **Pergunta de negócio** — que pergunta precisa ser respondida para essa decisão?
3. **Métrica** — que número responde? Qual a definição exata, quem é o dono dela?
4. **Granularidade** — em que nível o fato existe? (item de pedido? dia? loja?)
5. **Dimensões de análise** — por quais eixos se corta?
6. **Origem** — de que sistema vem, com que latência, com que qualidade?
7. **Regras de negócio** — cálculos, exceções, reprocessamentos, cortes de período.
8. **Público e distribuição** — quem consome, em que dispositivo, com que segurança.

**Artefatos mínimos** de um levantamento decente:

- **Matriz de barramento** (processo de negócio × dimensão conformada) — o mapa da arquitetura.
- **Dicionário de métricas** — nome, definição em português, fórmula, granularidade, dono,
  fonte, frequência de atualização.
- **Mapa de origem→destino** por campo, com regra de transformação.
- **Critérios de aceite** verificáveis: "Faturamento de mar/2026 bate com o razão contábil
  com diferença < 0,1%".
- **Requisitos não-funcionais**: volume, janela de atualização, latência aceitável, retenção,
  número de usuários simultâneos, requisitos de auditoria.

**Perguntas que revelam armadilhas cedo:**

- Existe mais de uma definição desse indicador na empresa hoje? Quem decide qual vale?
- O que acontece com registros que mudam retroativamente?
- Qual o comportamento esperado para "sem dados": zero, branco ou erro?
- Que decisão hoje é tomada em planilha paralela — e por quê?
- Quem assina que o número está certo?

Se essas cinco não têm resposta, o modelo semântico ainda não pode ser desenhado.

---

## Camadas de dados

O nome muda (raw/curated/semantic/consumption, bronze/silver/gold, staging/DW/marts), o
princípio não: **cada camada tem um dono, um contrato e um motivo para existir**.

| Camada               | Conteúdo                                                  | Contrato                     | Quem consome                |
| -------------------- | --------------------------------------------------------- | ---------------------------- | --------------------------- |
| **Raw / Bronze**     | Cópia fiel da origem, append-only, sem regra de negócio   | Fidelidade e rastreabilidade | Engenharia                  |
| **Curated / Silver** | Limpo, tipado, deduplicado, conformado, chaves resolvidas | Qualidade e integração       | Engenharia, cientistas      |
| **Semantic / Gold**  | Modelo dimensional + métricas de negócio                  | Semântica de negócio correta | Analistas, modelos Power BI |
| **Consumption**      | Relatórios, apps, APIs, exports                           | Experiência e performance    | Usuários finais             |

Regras que evitam o pântano:

- **Regra de negócio não sobe.** Se uma definição de métrica existe em três camadas, ela vai
  divergir. Defina o mais próximo possível da camada semântica e uma vez só.
- **Nada pula camada** sem decisão registrada. Relatório lendo direto do raw é dívida com juros.
- **Transformação o mais cedo possível, cálculo o mais tarde possível.** Limpeza e conformação
  em ETL; agregação e contexto de filtro em DAX.
- **Idempotência.** Reprocessar a mesma janela duas vezes tem que dar o mesmo resultado.

No stack Microsoft: Fabric Lakehouse/Warehouse ou banco relacional para raw/curated,
modelo semântico Power BI para a camada semântica, relatórios e apps para consumo. Power Query
resolve transformação leve; transformação pesada dentro do modelo é sinal de camada faltando.

---

## Modelagem dimensional

A camada semântica do Power BI é otimizada para **star schema**. Isso não é preferência
estilística — o motor VertiPaq e o mecanismo de propagação de filtro assumem esse formato.

- **Fato** — eventos mensuráveis, granularidade única e explícita, chaves estrangeiras + medidas
  aditivas. Nunca misture granularidades numa tabela de fatos.
- **Dimensão** — contexto descritivo, chave surrogate, atributos desnormalizados. Achatar
  hierarquias (categoria/subcategoria/produto numa tabela) é correto aqui.
- **Dimensão conformada** — a mesma dimensão servindo vários fatos. É o que permite comparar
  processos de negócio.
- **Dimensão degenerada** — número do pedido dentro do fato, sem tabela própria.
- **Role-playing** — a mesma dimensão em papéis diferentes (data do pedido / data de entrega):
  relacionamentos inativos + `USERELATIONSHIP`, ou cópias da dimensão quando a clareza importa
  mais que a memória.
- **SCD tipo 2** — historiza atributos com chave surrogate + vigência. Decida por atributo, não
  por dimensão inteira.
- **Bridge / factless fact** — relações muitos-para-muitos. Evite relacionamento M:N nativo
  quando uma bridge resolve com semântica mais previsível.
- **Snowflake** — normalização parcial. Aceitável em dimensões enormes com atributos raramente
  usados; caro em legibilidade. Justifique.

Sinais de que o modelo saiu do trilho: relacionamentos bidirecionais em toda parte, tabelas de
fatos se relacionando diretamente entre si, medidas cheias de `LOOKUPVALUE`, colunas calculadas
resolvendo o que deveria ser junção no ETL.

---

## A camada semântica

O modelo semântico é o contrato entre a engenharia de dados e o negócio. É onde o TMDL vive.

Responsabilidades que só ele pode cumprir:

- **Definição única de métrica** — a medida DAX é a fonte da verdade do cálculo.
- **Vocabulário de negócio** — nomes, descrições, pastas, formatos. O usuário nunca deve ver
  `dim_prod_sk`.
- **Segurança em nível de linha e de objeto** — RLS/OLS aplicados uma vez, valem para todos os
  consumidores.
- **Performance** — cardinalidade, tipos, agregações, modo de armazenamento.

Modelo **compartilhado** vs modelo **por relatório**: o compartilhado (endorsed, certificado)
evita divergência de números e é a escolha padrão em ambiente corporativo; o por-relatório é
aceitável para exploração e projetos de vida curta. Escolha explícita, não por inércia.

Checklist do que torna um modelo semântico "de produção": nomes em linguagem de negócio, todas
as colunas técnicas ocultas, descrições em todos os objetos expostos, `formatString` em todas as
medidas, `summarizeBy: none` em chaves, tabela de calendário marcada, relacionamentos
unidirecionais salvo exceção justificada, RLS testada, e o modelo versionado como pasta TMDL em
Git.

---

## TOGAF: capacidade de BI & Analytics

O _TOGAF Series Guide: Information Architecture — Business Intelligence & Analytics_ (2023)
trata BI como uma **capacidade** da arquitetura corporativa, não como um conjunto de ferramentas.
Estrutura do guia:

- **Cap. 1** — introdução; notação ArchiMate usada ao longo do documento.
- **Cap. 2** — a capacidade de BI & Analytics em visão de alto nível: modelo de referência de
  **funções de negócio** e **funções de aplicação**.
- **Cap. 3** — especialização do **ADM** (Architecture Development Method) para BI & Analytics e
  plataformas de dados, com síntese das ações por fase (Preliminar, A a G).
- **Cap. 4** — modelos de referência funcionais detalhados das capacidades.

Público-alvo: arquitetos corporativos e de dados.

### O que aproveitar na prática

**Pense em funções, não em produtos.** Antes de dizer "Power BI + Fabric", enumere as funções
que precisam existir (ingestão, qualidade, catalogação, modelagem, distribuição, self-service,
governança, monitoramento) e mapeie produto → função. Lacunas ficam visíveis; sobreposições
também.

**Use o ADM como roteiro de entrega**, adaptado ao ciclo de BI:

| Fase ADM                        | Tradução para BI                                                      |
| ------------------------------- | --------------------------------------------------------------------- |
| Preliminar                      | Princípios de dados, papéis, ferramentas, framework de governança     |
| A — Visão                       | Escopo, stakeholders, casos de decisão prioritários, visão do target  |
| B — Negócio                     | Processos de negócio, matriz de barramento, dicionário de métricas    |
| C — Sistemas (Dados/Aplicação)  | Modelo de dados por camada, catálogo, linhagem, aplicações analíticas |
| D — Tecnologia                  | Plataforma, capacidade, rede, segurança, custo                        |
| E — Oportunidades e soluções    | Agrupamento em pacotes de trabalho e ondas de entrega                 |
| F — Planejamento de migração    | Roadmap, dependências, coexistência com o legado                      |
| G — Governança de implementação | Conformidade das entregas com a arquitetura definida                  |

**Documente a arquitetura-alvo e o gap**, não só o estado atual. Um diagrama de "como é hoje"
sem "como deveria ser" e sem "o que falta" não sustenta decisão de investimento.

O guia usa **ArchiMate** como notação. Se o cliente não usa ArchiMate, não force — mas mantenha a
separação de camadas (negócio / aplicação / tecnologia) na representação escolhida.

---

## Governança e gestão de metadados

Governança de BI é, na prática, resposta a quatro perguntas:

1. **Quem pode criar?** Quem publica modelo compartilhado, quem cria relatório, quem só consome.
2. **O que é confiável?** Endosso e certificação de modelos, com critérios escritos.
3. **De onde veio?** Linhagem de origem até visual.
4. **Está certo?** Qualidade medida, não presumida.

### Gestão de metadados

Três tipos, todos necessários:

- **Técnico** — esquemas, tipos, partições, dependências. Extraível do próprio modelo (a pasta
  TMDL é uma fonte de metadados técnica de primeira qualidade).
- **De negócio** — definição de métrica, dono, glossário. Vive em descrições dos objetos, no
  dicionário de métricas e no catálogo.
- **Operacional** — histórico de refresh, falhas, uso, performance.

O TMDL permite embutir metadados de governança direto no modelo: `description` em todo objeto e
`annotation`/`extendedProperty` para dono, classificação e SLA. Sem catálogo corporativo, isso é
o suficiente para gerar documentação automática.

### Qualidade de dados

Dimensões clássicas — completude, acurácia, consistência, temporalidade, unicidade, validade.
Torne-as testes executáveis no pipeline, com limiar e responsável, e publique o resultado.
Qualidade não medida é qualidade não existente.

---

## Segurança

Camadas que precisam ser desenhadas juntas:

- **Acesso à plataforma** — quem entra no workspace, com que papel (Admin/Member/Contributor/Viewer).
- **Acesso ao item** — quem vê o modelo, quem vê o relatório; app de distribuição.
- **RLS** — filtro por linha, estático ou dinâmico via `USERPRINCIPALNAME()`.
- **OLS** — ocultação de colunas/tabelas por role.
- **Classificação e rótulos de sensibilidade** — herdados na exportação.
- **Credenciais de origem** — gateway, service principal, identidade gerenciada. Nunca
  credencial pessoal em produção.

Princípio operacional: **segurança pertence à camada semântica, não ao relatório**. Filtro em
visual não é segurança.

---

## Roadmap e maturidade

Escada útil para diagnosticar onde a organização está:

| Nível                    | Sintoma                                              | Próximo passo                                        |
| ------------------------ | ---------------------------------------------------- | ---------------------------------------------------- |
| 1 — Planilha             | Números divergem entre áreas; ninguém sabe qual vale | Definir dicionário de métricas e um dono por métrica |
| 2 — Relatório isolado    | Cada área tem seu PBIX com sua própria query         | Extrair camada curated e um modelo compartilhado     |
| 3 — Modelo compartilhado | Um modelo endossado, mas manual                      | Versionar em Git (PBIP/TMDL), automatizar deploy     |
| 4 — Engenharia           | CI/CD, testes, catálogo, linhagem                    | Métricas de uso e custo, otimização contínua         |
| 5 — Produto de dados     | Domínios com donos, contratos e SLA                  | Federação, self-service governado                    |

Roadmap honesto tem **ondas com valor entregue em cada uma**. Um roadmap que só entrega valor no
mês 12 não sobrevive à primeira troca de prioridade.

---

## Anti-padrões de arquitetura

| Anti-padrão                           | Por que dói                                        | Saída                                       |
| ------------------------------------- | -------------------------------------------------- | ------------------------------------------- |
| Modelo espelhando o OLTP              | Junções caras, filtros imprevisíveis, DAX ilegível | Star schema na camada semântica             |
| Regra de negócio no visual            | Impossível auditar, não reutiliza                  | Medida no modelo                            |
| Um modelo gigante para tudo           | Refresh longo, memória, blast radius               | Modelos por domínio + dimensões conformadas |
| Um modelo por relatório               | Definições divergem                                | Modelo compartilhado endossado              |
| Power Query como ETL corporativo      | Sem orquestração, sem teste, sem reuso             | Transformação na camada de dados            |
| Bidirecional por padrão               | Ambiguidade e lentidão                             | Unidirecional + `CROSSFILTER` pontual       |
| Coluna calculada para tudo            | Memória e refresh                                  | ETL ou medida                               |
| PBIX como fonte da verdade            | Sem diff, sem merge, sem histórico                 | PBIP com pasta TMDL em Git                  |
| Governança como comitê sem ferramenta | Vira reunião                                       | Regras automatizadas no pipeline            |
