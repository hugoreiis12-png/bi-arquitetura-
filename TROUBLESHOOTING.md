# Troubleshooting — bi-ide-architecture

Guia de solução de problemas comuns neste projeto.

## Índice

1. [Git e Versionamento](#git-e-versionamento)
2. [Power BI Desktop / PBIP](#power-bi-desktop--pbip)
3. [Tabular Editor](#tabular-editor)
4. [DAX Studio](#dax-studio)
5. [CI/CD Pipeline](#cicd-pipeline)
6. [MCP Server](#mcp-server)
7. [ORM SDK](#orm-sdk)
8. [Deploy e Publicação](#deploy-e-publicação)
9. [Docker e Containerização](#docker-e-containerização)
10. [Scripts e Automação](#scripts-e-automação)

---

## Git e Versionamento

### Conflitos de merge em arquivos TMDL

**Sintoma**: Conflitos ao fazer merge de branches que modificaram a mesma tabela.

**Solução**:
```bash
# 1. Abra o arquivo conflitante no VS Code
# 2. Resolva manualmente, preservando:
#    - lineageTag (NÃO altere)
#    - annotations existentes
#    - Ordem das colunas (evite reordenar)
# 3. Use ALM Toolkit para merge visual de datasets
```

**Prevenção**:
- Evite reordenar coleções sem necessidade
- Trabalhe em seções diferentes da mesma tabela
- Faça commits frequentes e pequenos

### Arquivo .pbix versionado acidentalmente

**Sintoma**: Arquivo `.pbix` aparece no `git status`.

**Solução**:
```bash
# Adicione ao .gitignore
echo "*.pbix" >> .gitignore

# Remova do tracking (se já foi commitado)
git rm --cached "*.pbix"
git commit -m "chore: remove .pbix do versionamento"
```

### lineageTag alterado sem necessidade

**Sintoma**: Diffs mostram mudanças em `lineageTag` que não foram intencionais.

**Solução**:
```bash
# Restaure o lineageTag original
git checkout HEAD -- src/datasets/Modelo.Dataset/definition/tabela.tmdl
```

**Prevenção**: Nunca edite `lineageTag` manualmente. Ele é gerenciado pelo Power BI.

---

## Power BI Desktop / PBIP

### Opção PBIP não aparece

**Sintoma**: `File → Save As` não mostra "Power BI Project (.pbip)".

**Solução**:
1. `File → Options → Preview features`
2. Ative "Power BI Project (.pbip) save mode"
3. Reinicie o Power BI Desktop
4. Verifique se a versão é ≥ 2.121

### Pasta .Dataset não é criada

**Sintoma**: Ao salvar como PBIP, apenas o arquivo `.pbip` é criado.

**Solução**:
1. Verifique se há pelo menos uma tabela no modelo
2. Salve novamente (o Desktop pode ter travado)
3. Verifique se o caminho não excede 260 caracteres

### Relatório não abre no Desktop após pull

**Sintoma**: Erro ao abrir `.Report` após clonar ou fazer pull.

**Solução**:
```bash
# Reabra o dataset primeiro
# O .Report referencia o .Dataset localmente

# Se persistir, delete a pasta .Report e reabra o .pbip
# O Desktop recriará a pasta .Report
```

### Alterações no relatório não são salvas

**Sintoma**: Mudanças no layout não aparecem após salvar.

**Solução**:
1. Verifique se está editando o `.Report` correto
2. Salve explicitamente (Ctrl+S)
3. Verifique se o `definition.pbism` está apontando para o dataset certo

---

## Tabular Editor

### Erro ao abrir modelo PBIP

**Sintoma**: Tabular Editor não reconhece a estrutura PBIP.

**Solução**:
1. Abra via `File → Open → pasta do .Dataset`
2. Ou arraste a pasta `.Dataset` para o Tabular Editor
3. Verifique se a versão é ≥ 2.20

### Scripts C# não executam

**Sintoma**: Erro de sintaxe ao rodar script C#.

**Solução**:
1. Verifique se está usando a sintaxe do Tabular Editor (não C# padrão)
2. Consulte a [documentação oficial](https://docs.tabulareditor.com/)
3. Use `Model.Tables["Nome"]` em vez de `Model.Table["Nome"]`

### Alterações não persistem

**Sintoma**: Mudanças feitas no Tabular Editor desaparecem.

**Solução**:
1. Clique em `Save` (não apenas `Apply`)
2. Verifique se o arquivo `.tmdl` foi modificado
3. Feche e reabra o modelo para confirmar

---

## DAX Studio

### Não conecta ao dataset

**Sintoma**: DAX Studio não lista o dataset do Desktop.

**Solução**:
1. Verifique se o Desktop está aberto com o modelo
2. Feche e reabra o DAX Studio
3. Tente `File → Connect → detectar automaticamente`
4. Verifique se há outro Power BI Desktop rodando

### Medida retorna erro de sintaxe

**Sintoma**: DAX inválido ao executar medida.

**Solução**:
```dax
-- Verifique:
-- 1. Parênteses balanceados
-- 2. Nomes de colunas entre colunas simples
-- 3. Uso correto de RELATED vs LOOKUPVALUE
-- 4. DIVIDE para divisões

-- Exemplo correto:
DIVIDE(
    SUM('Vendas'[Receita]),
    DISTINCTCOUNT('Vendas'[Pedido]),
    BLANK()
)
```

### Performance lenta ao profiler

**Sintoma**: Queries executadas pelo DAX Studio são lentas.

**Solução**:
1. Use "Server Timings" para analisar
2. Verifique se há `FILTER` sobre tabela inteira
3. Verifique cardinalidade dos relacionamentos
4. Considere usar `SUMMARIZE` em vez de `FILTER` + `GROUPBY`

---

## CI/CD Pipeline

### Pipeline falha na validação TMDL

**Sintoma**: Job `validate` falha com erro de compilação.

**Solução**:
```bash
# Teste localmente antes de push
scripts/compile-pbip.ps1

# Verifique:
# 1. Sintaxe TMDL correta
# 2. Referências entre tabelas
# 3. Tipos de dados
```

### DAX smoke tests falham

**Sintoma**: Job `dax-tests` falha.

**Solução**:
1. Execute os testes localmente
2. Verifique se as medidas existem no modelo
3. Verifique se os nomes das medidas estão corretos
4. Consulte `tests/dax/` para exemplos

### Deploy Dev não é disparado

**Sintoma**: Merge em `main` não triggera o deploy.

**Solução**:
1. Verifique se o push foi para `main`
2. Verifique se os arquivos alterados estão nos paths:
   - `src/**`
   - `tests/**`
3. Verifique se o workflow está habilitado
4. Consulte os logs do GitHub Actions

### Erro de autenticação no deploy

**Sintoma**: `azure/login@v2` falha com credenciais inválidas.

**Solução**:
1. Verifique os secrets:
   - `AZURE_SP_DEV_CLIENT_ID`
   - `AZURE_SP_DEV_CLIENT_SECRET`
   - `AZURE_TENANT_ID`
   - `AZURE_SUBSCRIPTION_ID`
2. Verifique se o Service Principal não expirou
3. Verifique se o SP tem permissão no workspace
4. Registre novas credenciais no Key Vault

### Workflow não aparece no GitHub

**Sintoma**: Pipeline não é listado em Actions.

**Solução**:
1. Verifique se o arquivo está em `.github/workflows/`
2. Verifique a sintaxe YAML
3. Verifique se o branch está correto
4. Force um push para re-trigger

---

## MCP Server

### Servidor não inicia

**Sintoma**: `powerbi-mcp` retorna erro ao iniciar.

**Solução**:
```bash
# Verifique as variáveis de ambiente
echo $PBI_TENANT_ID
echo $PBI_SP_CLIENT_ID
echo $PBI_SP_CLIENT_SECRET

# Teste com variáveis mínimas
PBI_TENANT_ID=xxx PBI_SP_CLIENT_ID=xxx PBI_SP_CLIENT_SECRET=xxx \
  powerbi-mcp --http --port 8000
```

### Tools não são listadas

**Sintoma**: Cliente MCP não vê as tools disponíveis.

**Solução**:
1. Verifique se o servidor está rodando
2. Acesse `http://localhost:8000/sse` no browser
3. Verifique se há erros nos logs
4. Reinicie o servidor

### Erro de autenticação com Power BI

**Sintoma**: Tools retornam erro 401 ou 403.

**Solução**:
1. Verifique se o Service Principal está correto
2. Verifique se o tenant ID está correto
3. Verifique se o SP tem permissão no workspace
4. Verifique se as APIs do Power BI estão habilitadas

### Rate limit atingido

**Sintoma**: Erro 429 (Too Many Requests).

**Solução**:
1. Aguarde o período de cooldown
2. Reduza a frequência de chamadas
3. Use batch operations quando disponível
4. Considere aumentar o rate limit no servidor

### DAX validation retorna falsos positivos

**Sintoma**: Medida被认为是 inválida mas funciona no Desktop.

**Solução**:
1. Verifique a versão do validador
2. Consulte as regras em `docs/ai-architecture/`
3. Reporte issue com exemplo mínimo reprodutível

---

## ORM SDK

### `pip install -e ".[dev]"` falha

**Sintoma**: Erro de instalação do powerbi-orm.

**Solução**:
```bash
# Verifique a versão do Python
python --version  # Deve ser >= 3.10

# Atualize pip
pip install --upgrade pip

# Instale dependências do sistema
pip install wheel setuptools

# Tente novamente
cd tools/orm
pip install -e ".[dev]"
```

### Conexão XMLA falha

**Sintoma**: ORM não consegue conectar via XMLA.

**Solução**:
1. Verifique se o workspace é Premium (XMLA requer Premium)
2. Verifique se a API XMLA está habilitada no tenant
3. Verifique as credenciais do Service Principal
4. Teste a conexão no DAX Studio primeiro

### TMDL gerado tem erros

**Sintoma**: TMDL gerado pelo ORM não compila.

**Solução**:
1. Verifique se os tipos de dados são válidos
2. Verifique se os nomes seguem convenções
3. Valide com `pbi-tools compile` antes de commitar
4. Consulte `docs/naming-conventions.md`

### Commit via ORM não funciona

**Sintoma**: `dataset.commit()` não cria commit.

**Solução**:
1. Verifique se o Git está configurado
2. Verifique se há mudanças staged
3. Verifique as permissões do repositório
4. Consulte os logs do ORM

---

## Deploy e Publicação

### Dataset não publica no workspace

**Sintoma**: `pbi-tools publish` falha.

**Solução**:
```bash
# Verifique o workspace ID
# Verifique as permissões do SP
# Teste com --verbose
pbi-tools publish ./src/datasets/Modelo.Dataset \
  --workspace $WORKSPACE_ID \
  --auth az \
  --verbose
```

### Refresh falha após deploy

**Sintoma**: Dataset publicado mas refresh retorna erro.

**Solução**:
1. Verifique as credenciais de conexão no Service
2. Verifique se os data sources estão acessíveis
3. Verifique se o gateway está configurado (se aplicável)
4. Consulte os logs no Power BI Service

### RLS não funciona no Service

**Sintoma**: Roles funcionam no Desktop mas não no Service.

**Solução**:
1. Verifique se as roles foram publicadas
2. Teste com "Exibir como" no Service
3. Verifique se os membros estão atribuídos corretamente
4. Verifique `securityFilteringBehavior` nos relacionamentos

### Workspace divergente entre ambientes

**Sintoma**: Dev e Test têm estruturas diferentes.

**Solução**:
1. Use o mesmo branch para deploy
2. Verifique se há branches desatualizados
3. Use Deployment Pipelines do Power BI
4. Automatize com `scripts/promote.ps1`

---

## Docker e Containerização

### Build da imagem falha

**Sintoma**: `docker build` retorna erro.

**Solução**:
```bash
# Verifique o Dockerfile
# Verifique se dependências estão no requirements.txt
# Limpe o cache
docker build --no-cache -t powerbi-mcp:latest .
```

### Container não inicia

**Sintoma**: `docker run` retorna erro imediatamente.

**Solução**:
```bash
# Verifique os logs
docker logs <container_id>

# Verifique as variáveis de ambiente
docker inspect <container_id>

# Teste interativamente
docker run -it powerbi-mcp:latest /bin/bash
```

### Porta já em uso

**Sintoma**: Erro "port is already allocated".

**Solução**:
```bash
# Encontre o processo usando a porta
netstat -tlnp | grep 8000

# Mude a porta
docker run -p 8001:8000 powerbi-mcp:latest
```

### ACR push falha

**Sintoma**: `az acr push` retorna erro de autenticação.

**Solução**:
```bash
# Logue no ACR
az acr login --name acrbi

# Verifique a imagem
docker tag powerbi-mcp:latest acrbi.azurecr.io/powerbi-mcp:1.0.0
docker push acrbi.azurecr.io/powerbi-mcp:1.0.0
```

---

## Scripts e Automação

### `scripts/bi` não funciona

**Sintoma**: Comando `bi` não é reconhecido.

**Solução**:
```bash
# Adicione ao PATH
export PATH="$PWD/scripts:$PATH"

# Ou execute diretamente
./scripts/bi doctor
```

### Bootstrap falha

**Sintoma**: `bootstrap-mcp-infra.ps1` retorna erro.

**Solução**:
1. Verifique se está logado no Azure (`az login`)
2. Verifique se tem permissões de Contributor
3. Verifique se a subscription está correta
4. Execute com `-WhatIf` primeiro

### Extract não gera documentação

**Sintoma**: `bi extract` roda mas não cria arquivos de docs.

**Solução**:
```bash
# Verifique se --generate-docs está habilitado
bi extract --workspace X --dataset Y --generate-docs

# Verifique se o diretório de saída existe
# Verifique as permissões de escrita
```

### Compile PBIP falha localmente

**Sintoma**: `scripts/compile-pbip.ps1` retorna erro.

**Solução**:
```bash
# Verifique se pbi-tools está instalado
dotnet tool list -g

# Instale se necessário
dotnet tool install --global Microsoft.PowerBI.Tools

# Execute com verbose
scripts/compile-pbip.ps1 -Verbose
```

---

## Ainda com problemas?

1. Consulte a documentação em `docs/`
2. Busque issues similares no GitHub
3. Abra nova issue com:
   - Passos para reproduzir
   - Comportamento esperado vs atual
   - Logs de erro
   - Ambiente (SO, versões)
4. Entre em contato com os mantenedores
