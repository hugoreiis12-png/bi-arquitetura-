# TOM, AMO, XMLA e automação de modelos semânticos

Como ler, escrever e implantar modelos por código. Leia antes de gerar C#, PowerShell ou Python
que toque em modelos — as assinaturas são específicas e errar de memória gera código que não
compila.

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Serializar um modelo para pasta TMDL](#serializar-um-modelo-para-pasta-tmdl)
3. [Implantar uma pasta TMDL](#implantar-uma-pasta-tmdl)
4. [Serialização de objeto para string](#serialização-de-objeto-para-string)
5. [Serialização por stream](#serialização-por-stream)
6. [Tratamento de erros](#tratamento-de-erros)
7. [Endpoint XMLA](#endpoint-xmla)
8. [Outras vias: PowerShell, Python, ferramentas](#outras-vias-powershell-python-ferramentas)
9. [CI/CD de modelos semânticos](#cicd-de-modelos-semânticos)

---

## Pré-requisitos

Referencie o pacote NuGet do **AMO** (Analysis Services Management Objects). A API TMDL vive em
`Microsoft.AnalysisServices.Tabular`; a serialização por stream em
`Microsoft.AnalysisServices.Tabular.Serialization`.

Para autoria e leitura de `.tmdl` fora do Desktop, instale a extensão TMDL do VS Code.

---

## Serializar um modelo para pasta TMDL

Do workspace (Premium/Fabric) para o disco:

```csharp
var workspaceXmla = "<endereço XMLA do workspace>";
var datasetName   = "<nome do modelo semântico>";
var outputPath    = System.Environment.CurrentDirectory;

using (var server = new Microsoft.AnalysisServices.Tabular.Server())
{
    server.Connect(workspaceXmla);

    var database = server.Databases.GetByName(datasetName);

    var destinationFolder = $"{outputPath}\\{database.Name}-tmdl";

    Microsoft.AnalysisServices.Tabular.TmdlSerializer
        .SerializeDatabaseToFolder(database.Model, destinationFolder);
}
```

Assinaturas da classe `TmdlSerializer`:

| Método                                                           | Efeito                                          |
| ---------------------------------------------------------------- | ----------------------------------------------- |
| `SerializeDatabaseToFolder(Database database, string path)`      | Grava a representação em pasta TMDL             |
| `DeserializeDatabaseFromFolder(string path)`                     | Lê a pasta e devolve o objeto `Database` do TOM |
| `DeserializeModelFromFolder(string path)`                        | Lê a pasta e devolve o `Model`                  |
| `SerializeObject(MetadataObject obj, bool qualifyObject = true)` | Devolve o texto TMDL de um objeto               |

Depois de serializar, edite os arquivos com qualquer editor de texto. Adicionar uma medida é
literalmente adicionar um bloco no `.tmdl` da tabela:

```tmdl
/// Sales data for year over year analysis
table Sales

    partition 'Sales-Part1' = m
        mode: Import
        source =
            let
                ...
            in
                #"Filtered Rows1"

    measure 'Sales Amount' = SUMX('Sales', [Quantity] * [Net Price])
        formatString: $ #,##0

    measure 'Sales Amount (Computers)' = CALCULATE([Sales Amount], 'Product'[Category] = "Computers")
        formatString: $ #,##0
```

---

## Implantar uma pasta TMDL

Do disco para o workspace:

```csharp
var xmlaServer     = "<endereço XMLA do workspace>";
var tmdlFolderPath = $"{System.Environment.CurrentDirectory}\\Contoso-tmdl";

var model = Microsoft.AnalysisServices.Tabular.TmdlSerializer
    .DeserializeModelFromFolder(tmdlFolderPath);

using (var server = new Microsoft.AnalysisServices.Tabular.Server())
{
    server.Connect(xmlaServer);

    using (var remoteDatabase = server.Databases[model.Database.ID])
    {
        model.CopyTo(remoteDatabase.Model);

        remoteDatabase.Model.SaveChanges();
    }
}
```

Pontos de atenção:

- `CopyTo` + `SaveChanges` aplica as **diferenças** de metadados; não move dados.
- Alterações estruturais (nova coluna, mudança de partição) deixam tabelas em estado não
  processado — programe o refresh na sequência.
- O `Database.ID` do destino precisa existir. Para criar do zero, adicione um novo `Database`
  à coleção do servidor antes de copiar.

---

## Serialização de objeto para string

Útil para diffs pontuais, documentação e para gerar trechos de script:

```csharp
var output = Microsoft.AnalysisServices.Tabular.TmdlSerializer
    .SerializeObject(model.Tables["Product"].Columns["ProductKey"], qualifyObject: true);

Console.WriteLine(output);
```

Saída:

```tmdl
ref table Product

    column ProductKey
        dataType: int64
        isKey
        formatString: 0
        isAvailableInMdx: false
        lineageTag: 4184d53e-cd2d-4cbe-b8cb-04c72a750bc4
        summarizeBy: none
        sourceColumn: ProductKey

        annotation SummarizationSetBy = Automatic
```

Note o `ref table Product` gerado por `qualifyObject: true` — é exatamente o que se cola dentro
de um `createOrReplace` para alterar a coluna sem redefinir a tabela.

---

## Serialização por stream

Converte objetos TOM em fluxos de bytes (armazenamento, transmissão, interoperabilidade) e —
mais importante na prática — **permite controlar quais documentos são lidos e gerados**.

Modelo inteiro em uma única variável de texto:

```csharp
var output = new StringBuilder();

foreach (Microsoft.AnalysisServices.Tabular.Serialization.MetadataDocument document in model.ToTmdl())
{
    using (TextWriter writer = new StringWriter(output))
    {
        document.WriteTo(writer);
    }
}
```

Desserializar seletivamente (aqui, ignorando roles — padrão útil quando a segurança é gerida
por ambiente e não deve vir do repositório):

```csharp
var context = Microsoft.AnalysisServices.Tabular.Serialization.MetadataSerializationContext
    .Create(MetadataSerializationStyle.Tmdl);

var files = Directory.GetFiles("[caminho da pasta TMDL]", "*.tmdl", SearchOption.AllDirectories);

foreach (var file in files)
{
    if (file.Contains("/roles/"))
        continue;

    using (TextReader reader = File.OpenText(file))
    {
        context.ReadFromDocument(file, reader);
    }
}

var model = context.ToModel();
```

Esse padrão é a base de deploys multiambiente: um repositório, filtros diferentes por destino.

---

## Tratamento de erros

Além das exceções .NET usuais (`ArgumentException`, `InvalidOperationException`), a API TMDL
lança duas específicas — e distingui-las economiza horas:

| Exceção                      | Significa                                                                                        | O que fazer                                                                                        |
| ---------------------------- | ------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `TmdlFormatException`        | Texto TMDL não é sintaxe válida (palavra-chave ou indentação inválida)                           | Corrigir o arquivo; o erro aponta linha exata                                                      |
| `TmdlSerializationException` | Sintaxe válida, mas viola a lógica de metadados do TOM (tipo de valor incompatível, por exemplo) | Corrigir a semântica: propriedade errada para o objeto, valor fora do enum, referência inexistente |

Ambas trazem `Document` (caminho do arquivo), `Line` (número da linha) e `LineText`.

```csharp
try
{
    var tmdlPath = "<caminho da pasta TMDL>";
    var model = Microsoft.AnalysisServices.Tabular.TmdlSerializer
        .DeserializeDatabaseFromFolder(tmdlPath);
}
catch (Microsoft.AnalysisServices.Tabular.Tmdl.TmdlFormatException ex)
{
    Console.WriteLine($"Erro ao desserializar TMDL '{ex.Message}', documento: '{ex.Document}', linha: '{ex.Line}', texto: '{ex.LineText}'");
    throw;
}
```

Em pipeline, capture as duas e falhe o build com o caminho + linha no log. Um `TmdlFormatException`
não reportado com localização é um debug de vinte minutos que deveria durar vinte segundos.

---

## Endpoint XMLA

O endpoint XMLA é a porta de entrada para tudo que é programático em workspaces Premium/Fabric:
AMO/TOM, TMSL, DAX Studio, Tabular Editor, SSMS, `Invoke-ASCmd`.

- Endereço: `powerbi://api.powerbi.com/v1.0/myorg/<nome do workspace>`.
- **Leitura** habilita conectar e consultar; **leitura/escrita** habilita deploy de metadados.
  É configuração de capacidade — sem escrita habilitada, o deploy falha por permissão, não por
  código.
- Autenticação de serviço via service principal é o caminho para pipeline.
- Nem todo modelo é editável por XMLA: modelos publicados a partir de PBIX com certos recursos
  podem entrar em estado somente leitura após alteração externa.

---

## Outras vias: PowerShell, Python, ferramentas

- **PowerShell** — módulo `SqlServer` (`Invoke-ASCmd`) para TMSL; ou carregue os assemblies AMO
  e use o mesmo TOM do C#. Bom para pipelines que já vivem em PowerShell.
- **Python** — `pythonnet` carregando os assemblies AMO, ou bibliotecas de comunidade
  (`sempy`/semantic-link em notebooks Fabric). Para leitura e auditoria de pastas TMDL,
  parsing direto do texto costuma ser mais simples que carregar o TOM — veja
  `scripts/tmdl_audit.py`.
- **Tabular Editor** — CLI com script C# para automação de build e regras de Best Practice
  Analyzer no pipeline.
- **ALM Toolkit** — comparação e deploy seletivo de metadados entre modelos.

Ao recomendar uma dessas, deixe claro o que é da Microsoft e o que é ferramenta de comunidade —
a diferença importa em ambiente corporativo com política de software.

---

## CI/CD de modelos semânticos

Arquitetura de referência que funciona:

```
repositório Git
└── src/<Modelo>.SemanticModel/definition/   ← pasta TMDL (fonte da verdade)
    ├── database.tmdl / model.tmdl
    ├── tables/*.tmdl
    └── roles/*.tmdl                          ← muitas vezes filtrado no deploy

pipeline
 1. lint       → parse da pasta TMDL, falha em erro de formato/semântica
 2. regras     → Best Practice Analyzer / auditoria própria (ver scripts/tmdl_audit.py)
 3. build      → desserializa TMDL → objeto TOM
 4. deploy     → CopyTo + SaveChanges no XMLA do workspace de destino
 5. pós-deploy → refresh (completo ou por tabela), teste de fumaça em DAX
```

Decisões que precisam ser tomadas explicitamente:

- **Parametrização por ambiente.** Servidor/banco vivem em `expressions.tmdl` como parâmetros M.
  Substitua no deploy (por token replacement ou por filtro de documento na desserialização) em
  vez de manter branches divergentes.
- **Roles por ambiente.** Segurança de produção raramente deve vir do repositório de dev.
  Filtre `roles/` na desserialização e gerencie no destino.
- **Refresh não é deploy.** Separe os estágios; deploy que sempre dispara refresh completo
  inviabiliza entregas frequentes em modelos grandes.
- **Estratégia de branch.** Pastas TMDL fazem merge bem porque cada tabela é um arquivo. Ainda
  assim, dois desenvolvedores editando a mesma tabela conflitam — divida por tabela, não por
  medida.
- **`ref` e ordenação.** Sem ordenação determinística, cada round-trip gera diff de ruído. Se
  o diff está grande sem mudança semântica, é sintoma disso.
- **O que não versionar.** `.pbi/cache.abf` e `.pbi/localSettings.json` — sempre fora.

**Integração Git do Fabric**: sincroniza itens do workspace com um repositório. Atenção ao
detalhe operacional: a configuração **inicial** não traz os scripts salvos do TMDL View do modelo
publicado.
