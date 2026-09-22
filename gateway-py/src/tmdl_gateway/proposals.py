"""Store de propostas pull/bulk (arquivo JSON, TTL 30min).

Proposta registra intenção + hash do estado. `apply` sem `accept:true` ou com
proposal expirada/ausente falha sem escrever nada.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path


PROPOSAL_TTL_SECONDS = 30 * 60
MAX_FILES = 200
MAX_BYTES = 2 * 1024 * 1024

BLOCKED_SEGMENTS = (".pbi/cache.abf", ".pbi/localsettings.json")


class ProposalError(Exception):
    pass


def _store_dir(repo: Path) -> Path:
    d = Path(repo) / ".gateway" / "proposals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> float:
    return time.time()


def create_proposal(
    repo: str | Path,
    kind: str,
    workspace: str,
    dataset: str,
    files: list[dict],
    inventory: dict | None = None,
    findings_high: int = 0,
    extra: dict | None = None,
) -> dict:
    """Cria proposta somente-leitura (não escreve definition/)."""
    repo_p = Path(repo)
    total_bytes = sum(int(f.get("bytes", 0)) for f in files)
    if len(files) > MAX_FILES:
        raise ProposalError(f"proposta excede {MAX_FILES} arquivos ({len(files)})")
    if total_bytes > MAX_BYTES:
        raise ProposalError(f"proposta excede {MAX_BYTES} bytes ({total_bytes})")
    for f in files:
        rel = str(f.get("path", "")).replace("\\", "/").lower()
        if any(seg.lower() in rel for seg in BLOCKED_SEGMENTS):
            raise ProposalError(f"arquivo bloqueado na proposta: {f.get('path')}")
    payload = json.dumps(
        {"kind": kind, "workspace": workspace, "dataset": dataset, "files": files},
        sort_keys=True,
    )
    pid = f"prp_{uuid.uuid4().hex[:12]}"
    record = {
        "proposal_id": pid,
        "kind": kind,
        "workspace": workspace,
        "dataset": dataset,
        "files": files,
        "inventory": inventory or {},
        "findings_high": findings_high,
        "hash": hashlib.sha256(payload.encode()).hexdigest()[:16],
        "created_at": _now(),
        "expires_at": _now() + PROPOSAL_TTL_SECONDS,
        "applied": False,
        "extra": extra or {},
    }
    (_store_dir(repo_p) / f"{pid}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def load_proposal(repo: str | Path, proposal_id: str) -> dict:
    p = _store_dir(Path(repo)) / f"{proposal_id}.json"
    if not p.is_file():
        raise ProposalError(f"proposal não encontrada: {proposal_id}")
    record = json.loads(p.read_text(encoding="utf-8"))
    if record.get("applied"):
        raise ProposalError(f"proposal já aplicada (idempotência): {proposal_id}")
    if _now() > float(record.get("expires_at", 0)):
        raise ProposalError(f"proposal expirada: {proposal_id}")
    return record


def mark_applied(repo: str | Path, proposal_id: str) -> dict:
    record = load_proposal(repo, proposal_id)
    record["applied"] = True
    record["applied_at"] = _now()
    (_store_dir(Path(repo)) / f"{proposal_id}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record
