// src_agent/gateway/prompt-validator.ts
// Validação de argumentos de prompts MCP antes de enviar ao servidor
// Mitiga: cliente passando '$1' ou strings inválidas → erro claro no lado cliente

export interface PromptSchema {
  [paramName: string]: "int" | "string" | "float" | "boolean";
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

// Esquemas conhecidos de prompts (manutenção: adicionar novos conforme aparecerem)
const PROMPT_SCHEMAS: Record<string, PromptSchema> = {
  "review_measure": {
    pr_number: "int",
  },
  "explain_measure": {
    measure_name: "string",
  },
};

/**
 * Valida argumentos de um prompt contra seu schema conhecido.
 * @param promptName - Nome do prompt (ex: review_measure)
 * @param args - Argumentos passados ao prompt
 * @returns Resultado da validação com lista de erros
 */
export function validatePromptArgs(
  promptName: string,
  args: Record<string, unknown>
): ValidationResult {
  const errors: string[] = [];
  const schema = PROMPT_SCHEMAS[promptName];

  // Se não temos schema, passar (prompt novo ou desconhecido)
  if (!schema) {
    console.warn(`[PromptValidator] Esquema desconhecido para prompt: ${promptName}`);
    return { valid: true, errors: [] };
  }

  for (const [paramName, expectedType] of Object.entries(schema)) {
    const value = args[paramName];

    // Parâmetro não fornecido é erro
    if (value === undefined) {
      errors.push(`${paramName}: parâmetro obrigatório não fornecido`);
      continue;
    }

    // Validar tipo
    const error = validateType(paramName, value, expectedType);
    if (error) {
      errors.push(error);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Valida um valor individual contra um tipo esperado.
 * Detecção especial de placeholders shell ('$1', etc.)
 */
function validateType(
  paramName: string,
  value: unknown,
  expectedType: string
): string | null {
  // Detectar placeholders shell — sempre inválido
  if (typeof value === "string") {
    if (/^\$\d+$/.test(value)) {
      return (
        `${paramName}: valor "${value}" parece ser placeholder shell ` +
        `— use valor real (ex: "42" para int, "medida_name" para string)`
      );
    }
    if (/^\{\{.*\}\}$/.test(value)) {
      return `${paramName}: valor "${value}" parece ser template {{...}} — use valor real`;
    }
  }

  switch (expectedType) {
    case "int":
      if (typeof value === "number") {
        if (!Number.isInteger(value)) {
          return `${paramName}: esperado int, recebido float ${value}`;
        }
        return null;
      }
      if (typeof value === "string") {
        // Aceitar string numérica para coerção
        if (/^-?\d+$/.test(value)) {
          return null;
        }
        return `${paramName}: esperado int, recebido string não-numérica "${value}"`;
      }
      return `${paramName}: esperado int, recebido ${typeof value}`;

    case "float":
      if (typeof value === "number") {
        return null;
      }
      if (typeof value === "string") {
        if (/^-?\d+\.?\d*$/.test(value)) {
          return null;
        }
        return `${paramName}: esperado float, recebido string não-numérica "${value}"`;
      }
      return `${paramName}: esperado float, recebido ${typeof value}`;

    case "string":
      if (typeof value === "string") {
        return null;
      }
      return `${paramName}: esperado string, recebido ${typeof value}`;

    case "boolean":
      if (typeof value === "boolean") {
        return null;
      }
      if (value === "true" || value === "false") {
        return null; // string que pode ser coerced
      }
      return `${paramName}: esperado boolean, recebido ${typeof value}`;

    default:
      return null;
  }
}

/**
 * Coercer argumentos para tipos corretos (string → int, etc.)
 * Mantém valores já corretos; não força conversão duvidosa.
 */
export function coercePromptArgs(
  promptName: string,
  args: Record<string, unknown>
): Record<string, unknown> {
  const schema = PROMPT_SCHEMAS[promptName];
  if (!schema) return args;

  const coerced = { ...args };

  for (const [paramName, expectedType] of Object.entries(schema)) {
    const value = coerced[paramName];
    if (value === undefined) continue;

    if (expectedType === "int" && typeof value === "string") {
      const num = parseInt(value, 10);
      if (!isNaN(num)) {
        coerced[paramName] = num;
      }
    } else if (expectedType === "float" && typeof value === "string") {
      const num = parseFloat(value);
      if (!isNaN(num)) {
        coerced[paramName] = num;
      }
    } else if (expectedType === "boolean" && typeof value === "string") {
      coerced[paramName] = value === "true" || value === "1";
    }
  }

  return coerced;
}
