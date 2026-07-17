# DAX Tests

> Pasta destinada a **smoke tests** e **validações de regras de negócio** em DAX.

## Como organizar

- **Numere os arquivos** (`01-`, `02-`, ...) para definir ordem de execução
- **Um arquivo por tema**: smoke tests, regras de negócio, cálculos críticos
- **Documente o objetivo** no topo de cada arquivo

## Como executar localmente

1. Abra o DAX Studio
2. Conecte ao modelo (Power BI Desktop local ou workspace)
3. Abra o arquivo `.dax` e execute

## Como executar no CI

O pipeline `bi-ci-cd.yml` lê os arquivos em `tests/dax/*.dax` e os executa em ordem.
Se algum `EVALUATE` retornar erro, o pipeline falha.

## Padrão de smoke test

```dax
EVALUATE
ROW(
    "Nome do Teste", <condição que retorna "OK" ou descrição do erro>
)
```

## Boas práticas

- ✅ Use medidas nomeadas em vez de cálculos inline (reutilização)
- ✅ Teste casos extremos: dataset vazio, filtros conflitantes, datas futuras
- ❌ Não faça testes que dependam de volume específico de dados (frágil)
- ❌ Não use `FILTER` pesado — smoke tests devem ser rápidos
