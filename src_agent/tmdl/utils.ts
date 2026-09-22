// src_agent/tmdl/utils.ts — Utilitários para o módulo TMDL

/**
 * Contador genérico — port fiel de collections.Counter do Python
 */
export class Counter<T extends string | number> {
  map = new Map<T, number>();

  inc(key: T, value: number = 1): void {
    this.map.set(key, (this.map.get(key) ?? 0) + value);
  }

  get(key: T): number {
    return this.map.get(key) ?? 0;
  }

  toObject(): Record<string, number> {
    const obj: Record<string, number> = {};
    for (const [k, v] of this.map) {
      obj[String(k)] = v;
    }
    return obj;
  }
}
