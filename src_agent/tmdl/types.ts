// src_agent/tmdl/types.ts — Tipos TypeScript para o parser e engine de auditoria TMDL
// Port fiel de tmdl.py + tmdl_tools.py

/** Nó da árvore TMDL parseada */
export interface TmdlNode {
  kind: string;
  name: string;
  expr: string | null;
  props: Record<string, string>;
  children: TmdlNode[];
  description: string | null;
  file: string;
  line: number;
  _isref?: boolean;
}

/** Cria um novo nó TMDL */
export function createNode(
  kind: string,
  name: string,
  opts?: {
    expr?: string | null;
    description?: string | null;
    file?: string;
    line?: number;
  }
): TmdlNode {
  return {
    kind,
    name,
    expr: opts?.expr ?? null,
    props: {},
    children: [],
    description: opts?.description ?? null,
    file: opts?.file ?? "",
    line: opts?.line ?? 0,
  };
}

/** Obtém uma propriedade do nó (case-insensitive) */
export function nodeProp(node: TmdlNode, key: string, defaultVal?: string): string | undefined {
  return node.props[key.toLowerCase()] ?? defaultVal;
}

/** Retorna filhos de um determinado kind */
export function nodeKids(node: TmdlNode, kind: string): TmdlNode[] {
  return node.children.filter((c) => c.kind === kind);
}

/** Regra de auditoria declarativa (JSON) */
export interface Rule {
  id: string;
  titulo: string;
  escopo: string;
  severidade: "baixa" | "media" | "alta";
  quando: RuleCondition;
  porque?: string;
  correcao?: string;
}

/** Condição declarativa — pode ser composta (E, OU, NÃO) ou atômica */
export type RuleCondition =
  | { e: RuleCondition[] }
  | { ou: RuleCondition[] }
  | { nao: RuleCondition }
  | { faltaPropriedade: string | string[] }
  | { temPropriedade: string | string[] }
  | { propriedadeIgual: Record<string, string> }
  | { propriedadeDiferente: Record<string, string> }
  | { propriedadePresenteEDiferente: Record<string, string> }
  | { propriedadeEm: Record<string, string[]> }
  | { nomeContemToken: string | string[] }
  | { nomeCasaRegex: string }
  | { nomeComecaCom: string | string[] }
  | { semDescricao: boolean }
  | { temExpressao: boolean }
  | { expressaoContem: string | string[] }
  | { expressaoLinhasMaiorQue: number }
  | { semFilhos: string }
  | { temFilhos: string }
  | { naoRelacionada: boolean }
  | { nomeDuplicadoNoModelo: boolean }
  | { contagemFilhosMaiorQue: [string, number] }
  | { medidaComLookups: boolean };
  

/** Achado de uma regra violada */
export interface Finding {
  id: string;
  titulo: string;
  severidade: string;
  porque?: string;
  correcao?: string;
  quantidade: number;
  itens: string[];
}

/** Inventário do modelo parseado */
export interface Inventory {
  database: string | null;
  compatibilityLevel: string | null;
  culture: string | null;
  tabelas: number;
  tabelas_ocultas: number;
  colunas: number;
  colunas_ocultas: number;
  colunas_calculadas: number;
  medidas: number;
  relacionamentos: number;
  hierarquias: number;
  particoes: number;
  modos_de_particao: Record<string, number>;
  roles: number;
  perspectivas: number;
  culturas: number;
  expressoes_compartilhadas: number;
  grupos_de_calculo: number;
  arquivos_tmdl: number;
}

/** Detalhe de uma tabela para o relatório */
export interface TableDetail {
  tabela: string;
  descricao: string | null;
  oculta: boolean;
  colunas: number;
  medidas: number;
  hierarquias: number;
  particoes: [string, string][];
  arquivo: string;
}

/** Índices auxiliares para avaliação de regras */
export interface AuditIndex {
  tabelas_relacionadas: Set<string>;
  contagem_nomes: Map<string, number>;
}

/** Alvo avaliável pela engine de regras */
export interface Target {
  node: TmdlNode;
  kind: string;
  pai?: TmdlNode;
  rotulo: string;
  contexto?: Record<string, unknown>;
}

/** Convenções do projeto */
export interface Conventions {
  [key: string]: unknown;
  idioma: string | null;
  tokens: Record<string, string[]>;
  nomenclatura: Record<string, unknown>;
  modelo: Record<string, unknown>;
  auditoria: {
    regrasDesativadas: Record<string, string>;
    severidadeMinima: string;
  };
}

/** Resultado completo da auditoria */
export interface AuditResult {
  inventario: Inventory;
  tabelas: TableDetail[];
  achados: Finding[];
  convencoes: string | null;
  regras: string;
  resumo: {
    total_ocorrencias: number;
    regras_violadas: number;
    alta: number;
    media: number;
    baixa: number;
  };
}

/** Documentos TMDL parseados (caminho relativo → nós raiz) */
export type TmdlDocs = Record<string, TmdlNode[]>;
