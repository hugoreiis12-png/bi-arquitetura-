"""CLI do gateway (chamada pela fachada TS). Saída sempre JSON no stdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .gateway import Gateway, GatewayError


def _out(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def _err(msg: str) -> int:
    print(json.dumps({"error": msg}, ensure_ascii=False))
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tmdl-gateway")
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pull-propose")
    p.add_argument("--workspace", required=True)
    p.add_argument("--dataset", required=True)

    p = sub.add_parser("pull-apply")
    p.add_argument("--proposal", required=True)
    p.add_argument("--accept", action="store_true")
    p.add_argument("--dataset-dir", default=None, help="Destino (ex: src/datasets/Vendas.Dataset)")
    p.add_argument("--pbip-layout", action="store_true", help="Normaliza TOM->PBIP no destino")

    p = sub.add_parser("approval-request")
    p.add_argument("--action", default="tmdl_commit")
    p.add_argument("--target", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--requested-by", default="dev")

    p = sub.add_parser("approve")
    p.add_argument("--token", required=True)
    p.add_argument("--approver", required=True)

    p = sub.add_parser("commit")
    p.add_argument("--branch", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--approval", required=True)
    p.add_argument("--target-dataset", default=None)
    p.add_argument("--create-pr", action="store_true")

    p = sub.add_parser("dax-run")
    p.add_argument("--dataset-path", required=True)

    p = sub.add_parser("bulk-propose")
    p.add_argument("--workspace", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--operations", required=True, help="JSON array de operações")

    p = sub.add_parser("bulk-apply")
    p.add_argument("--proposal", required=True)
    p.add_argument("--accept", action="store_true")
    p.add_argument("--connection", required=True)

    args = ap.parse_args(argv)
    gw = Gateway(Path(args.repo))
    try:
        if args.cmd == "pull-propose":
            return _out(gw.pull_propose(args.workspace, args.dataset))
        if args.cmd == "pull-apply":
            return _out(gw.pull_apply(args.proposal, bool(args.accept), args.dataset_dir, bool(args.pbip_layout)))
        if args.cmd == "approval-request":
            return _out(gw.approval_request(args.action, args.target, args.reason, args.requested_by))
        if args.cmd == "approve":
            return _out(gw.approve(args.token, args.approver))
        if args.cmd == "commit":
            return _out(gw.commit(args.branch, args.message, args.approval, args.target_dataset, args.create_pr))
        if args.cmd == "dax-run":
            return _out(gw.dax_run_local(args.dataset_path))
        if args.cmd == "bulk-propose":
            return _out(gw.bulk_propose(args.workspace, args.dataset, json.loads(args.operations)))
        if args.cmd == "bulk-apply":
            return _out(gw.bulk_apply(args.proposal, bool(args.accept), args.connection))
    except GatewayError as exc:
        return _err(str(exc))
    except Exception as exc:  # noqa: BLE001 — contrato: CLI sempre devolve JSON
        return _err(f"{type(exc).__name__}: {exc}")
    return _err("comando desconhecido")


if __name__ == "__main__":
    sys.exit(main())
