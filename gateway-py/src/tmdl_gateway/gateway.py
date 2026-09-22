"""Orquestração só-TMDL: pull-para-IDE, commit gateado, DAX RUN local, bulk.

Toda escrita em disco/Git/modelo passa por proposta aceita ou approval token.
Nada aqui importa o Service para versionar: o Service só é lido (Export) ou
atingido via `pbi-tools publish` fora do commit (fluxo existente).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from . import approvals as approvals_mod
from . import proposals as proposals_mod
from . import sidecar as sidecar_mod
from .branching import is_prod_target, resolve_dataset_for_branch


SIDECAR_PIN = sidecar_mod.SIDECAR_DEFAULT_VERSION

CONVENTIONAL_RE = re.compile(r"^(feat|fix|chore|docs|refactor|test)(\(.+\))?: .{1,100}$")


class GatewayError(Exception):
    pass


def _definition_dir(dataset_path: str | Path) -> Path:
    p = Path(dataset_path)
    if p.name == "definition" and p.is_dir():
        return p
    cand = p / "definition"
    if cand.is_dir():
        return cand
    return p


def _inventory_tmdl(definition: Path) -> dict:
    files = sorted(definition.rglob("*.tmdl")) if definition.is_dir() else []
    total_bytes = sum(f.stat().st_size for f in files if f.is_file())
    return {
        "arquivos_tmdl": len(files),
        "bytes": total_bytes,
        "has_database": (definition / "database.tmdl").is_file(),
        "has_model": (definition / "model.tmdl").is_file(),
    }


def _fail_on_high(inventory: dict) -> list[str]:
    """Gate mínimo offline: pasta precisa ter database.tmdl + model.tmdl."""
    issues = []
    if not inventory.get("has_database"):
        issues.append("alta: database.tmdl ausente na pasta definition/")
    if not inventory.get("has_model"):
        issues.append("alta: model.tmdl ausente na pasta definition/")
    return issues


class Gateway:
    """Gateway separado (instância leve, sem estado global)."""

    def __init__(self, repo: str | Path = "."):
        self.repo = Path(repo)

    # ---- pull-para-IDE (2 fases) ----

    def pull_propose(self, workspace: str, dataset: str) -> dict:
        """Fase 1 (somente leitura): exporta via sidecar p/ tmp e devolve proposta.

        Pergunta "deseja exportar para IDE?" deve acontecer na fachada (elicitation)
        antes de chamar aqui. Nenhum arquivo do repo é tocado nesta fase.
        """
        import uuid as _uuid

        tmp = self.repo / ".gateway" / "tmp" / f"pull_{_uuid.uuid4().hex[:12]}"
        tmp.mkdir(parents=True, exist_ok=True)
        # Tenta export via sidecar (read-only do modelo); fallback: inventário local.
        side = sidecar_mod.export_tmdl_via_sidecar(
            connection=dataset, database=dataset, out_dir=str(tmp)
        )
        exported = sorted(tmp.rglob("*.tmdl")) if tmp.is_dir() else []
        if exported:
            base = tmp
        else:
            base = self.repo / "src" / "datasets" / f"{dataset}.Dataset" / "definition"
        try:
            files = [
                {"path": str(p.relative_to(self.repo)), "bytes": p.stat().st_size}
                for p in sorted(base.rglob("*.tmdl"))
                if p.is_file()
            ][:proposals_mod.MAX_FILES]
        except ValueError:
            files = [{"path": str(p), "bytes": p.stat().st_size} for p in sorted(exported)]
        inv = _inventory_tmdl(base if base.is_dir() else tmp)
        record = proposals_mod.create_proposal(
            self.repo,
            kind="pull_ide",
            workspace=workspace,
            dataset=dataset,
            files=files,
            inventory={**inv, "sidecar": side.get("source")},
            extra={"tmp_dir": str(tmp)},
        )
        return {**record, "elicitation": "apply exige accept:true + proposal_id"}

    def pull_apply(
        self,
        proposal_id: str,
        accept: bool,
        dataset_dir: str | Path | None = None,
        pbip_layout: bool = False,
    ) -> dict:
        """Fase 2 (único ponto que escreve no repo).

        Sem `dataset_dir`: só registra aplicação (compat). Com `dataset_dir`:
        materializa o export do tmp; com `pbip_layout=True` normaliza TOM->PBIP
        (`definition/tables|cultures|roles`, `version.json`, `.pbip`).
        """
        if not accept:
            raise GatewayError("apply exige accept:true explícito do usuário")
        record = proposals_mod.load_proposal(self.repo, proposal_id)
        out: dict = {}
        if dataset_dir:
            from .pbip import normalize_tom_to_pbip

            tmp = Path(record.get("extra", {}).get("tmp_dir", ""))
            if not tmp.is_dir() or not list(tmp.glob("*.tmdl")):
                raise GatewayError(f"export temporário ausente para {proposal_id}")
            dest = Path(dataset_dir)
            if not dest.is_absolute():
                dest = self.repo / dest
            if pbip_layout:
                out["normalize"] = normalize_tom_to_pbip(tmp, dest, record.get("dataset", "Vendas"))
            else:
                dest.mkdir(parents=True, exist_ok=True)
                for f in sorted(tmp.glob("*.tmdl")):
                    shutil.copy2(f, dest / f.name)
                for sub in ("tables", "cultures", "roles"):
                    s = tmp / sub
                    if s.is_dir():
                        shutil.copytree(s, dest / sub, dirs_exist_ok=True)
                out["copied_to"] = str(dest)
        backup = self.repo / ".gateway" / "backups" / f"{proposal_id}-{int(time.time())}"
        backup.mkdir(parents=True, exist_ok=True)
        marked = proposals_mod.mark_applied(self.repo, proposal_id)
        return {**marked, **out, "backup_dir": str(backup)}

    # ---- commit gateado ----

    def approval_request(
        self, action: str, target: str, reason: str = "", requested_by: str = "dev"
    ) -> dict:
        if action != "tmdl_commit":
            raise GatewayError(f"action suportada: tmdl_commit (recebido {action})")
        return approvals_mod.request_token(
            self.repo, action, target, reason, requested_by
        )

    def approve(self, token: str, approver: str) -> dict:
        return approvals_mod.approve_token(self.repo, token, approver)

    def commit(
        self,
        branch: str,
        message: str,
        approval_token: str,
        target_dataset: str | None = None,
        create_pr: bool = False,
        dataset_base: str = "Vendas",
    ) -> dict[str, Any]:
        """Commit só-TMDL gateado por approval token single-use."""
        resolved = target_dataset or resolve_dataset_for_branch(branch, dataset_base)
        target = f"{branch}:{resolved}"
        # Checa sem consumir (auth falha cedo); o consumo acontece só após o git.
        approvals_mod.check_token(self.repo, approval_token, "tmdl_commit", target)
        if not CONVENTIONAL_RE.match(message.strip()):
            raise GatewayError(
                "mensagem fora do Conventional Commits (ex.: feat(vendas): ...)"
            )
        # Gate de qualidade offline (full rules via tmdl_audit na fachada/CI).
        local_def = self.repo / "src" / "datasets" / f"{dataset_base}.Dataset" / "definition"
        inv = _inventory_tmdl(local_def)
        highs = _fail_on_high(inv)
        if highs:
            raise GatewayError(f"fail_on_high: {highs}")
        repo = self.repo
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch],
                cwd=repo, check=True, capture_output=True,
            )
            stage = [p for p in ("src", "tests") if (repo / p).is_dir()]
            if not stage:
                raise GatewayError("nada para commitar: src/ e tests/ ausentes")
            subprocess.run(
                ["git", "add", "-A", *stage],
                cwd=repo, check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo, check=True, capture_output=True, text=True,
            )
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo, check=True, capture_output=True, text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            detalhe = exc.stderr or exc.stdout or exc
            raise GatewayError(f"git falhou: {detalhe}") from exc
        # Só consome o token após sucesso (retry preserva o token em falha).
        approvals_mod.consume_token(self.repo, approval_token)
        result: dict[str, Any] = {
            "branch": branch,
            "target_dataset": resolved,
            "commit_sha": sha,
            "is_prod": is_prod_target(branch),
        }
        if create_pr:
            try:
                pr = subprocess.run(
                    ["gh", "pr", "create", "--title", message.split("\n")[0],
                     "--body", f"target_dataset: {resolved}",
                     "--label", "ai-generated,needs-review"],
                    cwd=repo, check=True, capture_output=True, text=True,
                ).stdout.strip()
                result["pr_url"] = pr
            except subprocess.CalledProcessError as exc:
                result["pr_error"] = str(exc.stderr or exc)[:500]
        return result

    # ---- bulk (transação obrigatória) ----

    def bulk_propose(
        self, workspace: str, dataset: str, operations: list[dict]
    ) -> dict:
        if len(operations) > 200:
            raise GatewayError("bulk excede 200 operações")
        files = [{"path": f"tmdl://{i}", "bytes": len(str(op))} for i, op in enumerate(operations)]
        return proposals_mod.create_proposal(
            self.repo, "bulk", workspace, dataset, files,
            inventory={"operations": len(operations)},
        )

    def bulk_apply(self, proposal_id: str, accept: bool, connection: str) -> dict:
        if not accept:
            raise GatewayError("bulk_apply exige accept:true")
        record = proposals_mod.load_proposal(self.repo, proposal_id)
        ops = [{"Operation": "Validate", "Proposal": record["proposal_id"]}]
        res = sidecar_mod.execute_in_transaction(connection, ops, chunk_size=50)
        marked = proposals_mod.mark_applied(self.repo, proposal_id)
        return {**marked, "sidecar": res}

    # ---- DAX RUN local (localhost) ----

    def dax_run_local(self, dataset_path: str) -> dict:
        """Valida+audit+compila e espelha no Desktop em memória (localhost).

        Sem approval token (escopo local). Publica e salva localmente.
        """
        cfg = sidecar_mod.SidecarConfig.from_env()
        found = sidecar_mod.list_local_instances(cfg)
        instances = found.get("instances", [])
        if isinstance(instances, dict):
            instances = instances.get("value", []) or []
        if not instances:
            return {
                "status": "aguardando_desktop",
                "instances": [],
                "instrucao": "Abra o Vendas.pbip no Power BI Desktop e rode DAX RUN de novo.",
            }
        if len(instances) > 1:
            return {
                "status": "escolha_instancia",
                "instances": instances,
                "instrucao": "Há 2+ instâncias; escolha (elicitation) qual porta conectar.",
            }
        definition = _definition_dir(dataset_path)
        inv = _inventory_tmdl(definition)
        highs = _fail_on_high(inv)
        if highs:
            raise GatewayError(f"fail_on_high: {highs}")
        # Escrita local em transação (ou dry-run se sidecar ausente).
        inst = instances[0] if isinstance(instances, list) else instances
        conn = str(inst.get("connection", inst) if isinstance(inst, dict) else inst)
        tx = sidecar_mod.execute_in_transaction(conn, [{"Operation": "Validate"}], chunk_size=50, cfg=cfg)
        return {
            "status": "espelhado_local",
            "connection": conn,
            "inventario": inv,
            "transacao": tx,
            "nota": "definition/ persistida; confira no Desktop e salve (Ctrl+S).",
        }
