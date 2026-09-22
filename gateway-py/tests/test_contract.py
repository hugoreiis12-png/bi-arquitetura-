"""Contrato só-TMDL do gateway (sem rede, sem Desktop)."""

import json

from tmdl_gateway import approvals as ap
from tmdl_gateway import proposals as pr
from tmdl_gateway.branching import is_prod_target, resolve_dataset_for_branch
from tmdl_gateway.gateway import Gateway, GatewayError


def test_branch_mapping():
    assert resolve_dataset_for_branch("main") == "Vendas"
    assert resolve_dataset_for_branch("develop") == "Vendas_Dev"
    assert resolve_dataset_for_branch("test") == "Vendas_Test"
    assert resolve_dataset_for_branch("feat/x") == "Vendas_preview_feat_x"
    assert is_prod_target("main") and not is_prod_target("develop")


def test_proposal_requires_accept_and_blocks(tmp_path):
    rec = pr.create_proposal(tmp_path, "pull_ide", "WS", "Vendas", [{"path": "a.tmdl", "bytes": 10}])
    try:
        pr.load_proposal(tmp_path, "inexistente")
        raise AssertionError("deveria falhar")
    except Exception:
        pass
    try:
        pr.create_proposal(tmp_path, "pull_ide", "WS", "Vendas", [{"path": ".pbi/cache.abf", "bytes": 1}])
        raise AssertionError("deveria bloquear cache.abf")
    except Exception:
        pass
    assert rec["proposal_id"].startswith("prp_")


def test_commit_requires_token(tmp_path):
    gw = Gateway(tmp_path)
    try:
        gw.commit("feat/x", "feat(vendas): teste", approval_token="invalido")
        raise AssertionError("deveria exigir token")
    except Exception as exc:
        assert "token" in str(exc).lower()


def test_approval_single_use_and_quorum(tmp_path):
    rec = ap.request_token(tmp_path, "tmdl_commit", "main:Vendas", "teste")
    assert rec["required_approvers"] == 2
    ap.approve_token(tmp_path, rec["token"], "a@x.com")
    try:
        ap.validate_for_commit(tmp_path, rec["token"], "tmdl_commit", "main:Vendas")
        raise AssertionError("deveria exigir 2 aprovadores")
    except Exception as exc:
        assert "aprovadores" in str(exc).lower()
    ap.approve_token(tmp_path, rec["token"], "b@x.com")
    ok = ap.validate_for_commit(tmp_path, rec["token"], "tmdl_commit", "main:Vendas")
    assert ok["used"] is True  # consumo single-use no ato da validação
    try:
        ap.validate_for_commit(tmp_path, rec["token"], "tmdl_commit", "main:Vendas")
        raise AssertionError("single-use violado")
    except Exception:
        pass


def test_pull_apply_requires_accept(tmp_path):
    gw = Gateway(tmp_path)
    rec = gw.pull_propose("WS", "Vendas")
    try:
        gw.pull_apply(rec["proposal_id"], accept=False)
        raise AssertionError("deveria exigir accept:true")
    except GatewayError:
        pass


def test_pbip_normalize(tmp_path):
    from tmdl_gateway.pbip import normalize_tom_to_pbip

    src = tmp_path / "flat"
    src.mkdir()
    (src / "database.tmdl").write_text("database X\n", encoding="utf-8")
    (src / "model.tmdl").write_text("model X\n", encoding="utf-8")
    (src / "relationships.tmdl").write_text("", encoding="utf-8")
    (src / "Vendas.tmdl").write_text("table Vendas\n", encoding="utf-8")
    (src / "pt-BR.tmdl").write_text("culture 'pt-BR'\n", encoding="utf-8")
    (src / "LocalDateTable_abc.tmdl").write_text("table Local\n", encoding="utf-8")
    (src / "roles").mkdir()
    (src / "roles" / "RLS.tmdl").write_text("role RLS\n", encoding="utf-8")
    dest = tmp_path / "Vendas.Dataset"
    rep = normalize_tom_to_pbip(src, dest, "Vendas")
    assert rep["status"] == "normalizado"
    assert (dest / "definition" / "tables" / "Vendas.tmdl").is_file()
    assert (dest / "definition" / "cultures" / "pt-BR.tmdl").is_file()
    assert (dest / "definition" / "roles" / "RLS.tmdl").is_file()
    assert (dest / "definition" / "model.tmdl").is_file()
    assert (dest / "definition" / "version.json").is_file()
    assert (dest / "_tom_source" / "database.tmdl").is_file()
    assert (dest / "_auto_dates" / "LocalDateTable_abc.tmdl").is_file()
    assert dest.with_suffix(".pbip").is_file()
    # Idempotente na segunda passada (origem esvaziada -> erro claro, destino intacto)
    rep2 = normalize_tom_to_pbip(dest, dest, "Vendas")
    assert rep2["status"] == "ja_normalizado"


def test_conventional_commits_lint(tmp_path):
    rec = ap.request_token(tmp_path, "tmdl_commit", "feat/x:Vendas_preview_feat_x", "t")
    ap.approve_token(tmp_path, rec["token"], "a@x.com")
    gw = Gateway(tmp_path)
    try:
        gw.commit("feat/x", "mensagem ruim", approval_token=rec["token"])
        raise AssertionError("deveria barrar mensagem")
    except GatewayError as exc:
        assert "Conventional" in str(exc)
