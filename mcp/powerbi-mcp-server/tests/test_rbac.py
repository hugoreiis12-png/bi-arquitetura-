"""Tests for RBAC and DLP."""

import pytest

from powerbi_mcp.guardrails import (
    DLPError,
    Permission,
    PermissionDeniedError,
    UserContext,
    check_permission,
    check_workspace_access,
    get_user_permissions,
    resolve_roles,
)


class TestRoleResolution:
    def test_resolve_known_role(self):
        roles = resolve_roles(roles=[], groups=["BI-AI-Developer"])
        assert "BI-AI-Developer" in roles

    def test_resolve_known_role_by_oid(self):
        roles = resolve_roles(
            roles=[],
            groups=["00000000-0000-0000-0000-000000000003"],  # BI-AI-Lead OID
        )
        assert "BI-AI-Lead" in roles

    def test_unknown_group_ignored(self):
        roles = resolve_roles(roles=[], groups=["unknown-group-id"])
        assert len(roles) == 0


class TestPermissions:
    def test_reader_permissions(self):
        perms = get_user_permissions(
            roles=[], groups=["BI-AI-Reader"]
        )
        assert Permission.READ_METADATA in perms
        assert Permission.READ_DATA in perms
        assert Permission.WRITE_MODEL not in perms
        assert Permission.DEPLOY_PROD not in perms

    def test_developer_can_write_model(self):
        perms = get_user_permissions(roles=[], groups=["BI-AI-Developer"])
        assert Permission.WRITE_MODEL in perms
        assert Permission.DEPLOY_PROD not in perms

    def test_steward_can_deploy_prod(self):
        perms = get_user_permissions(roles=[], groups=["BI-AI-Steward"])
        assert Permission.DEPLOY_PROD in perms
        assert Permission.REFRESH in perms
        assert Permission.MODIFY_RLS in perms

    def test_admin_has_all(self):
        perms = get_user_permissions(roles=[], groups=["BI-AI-Admin"])
        assert Permission.ADMIN in perms


class TestCheckPermission:
    def test_reader_can_read_metadata(self):
        user = UserContext(
            user_id="u1", email="u1@x.com", groups=["BI-AI-Reader"]
        )
        check_permission(user, Permission.READ_METADATA)  # Should not raise

    def test_reader_cannot_write_model(self):
        user = UserContext(
            user_id="u1", email="u1@x.com", groups=["BI-AI-Reader"]
        )
        with pytest.raises(PermissionDeniedError):
            check_permission(user, Permission.WRITE_MODEL)

    def test_wildcard_prefix_match(self):
        # pbi:read:* should match pbi:read:metadata
        user = UserContext(
            user_id="admin", email="a@x.com", groups=["BI-AI-Admin"]
        )
        check_permission(user, "pbi:anything:here")


class TestWorkspaceAccess:
    def test_developer_can_access_dev_workspace(self):
        user = UserContext(
            user_id="u1", email="u1@x.com", groups=["BI-AI-Developer"]
        )
        check_workspace_access(user, "bi-vendas-dev")  # Should not raise

    def test_developer_cannot_access_test_workspace(self):
        user = UserContext(
            user_id="u1", email="u1@x.com", groups=["BI-AI-Developer"]
        )
        with pytest.raises(PermissionDeniedError):
            check_workspace_access(user, "bi-vendas-test")

    def test_steward_can_access_any_workspace(self):
        user = UserContext(
            user_id="u1", email="u1@x.com", groups=["BI-AI-Steward"]
        )
        check_workspace_access(user, "bi-vendas-prod")
        check_workspace_access(user, "bi-rh-test")
        check_workspace_access(user, "bi-anything")


class TestDLP:
    def test_cpf_detected(self):
        from powerbi_mcp.guardrails.dlp import DLPChecker

        checker = DLPChecker(enabled=True, bypass_roles=["BI-AI-Admin"])
        with pytest.raises(DLPError) as exc:
            checker.check_input(
                "SELECT * FROM clientes WHERE cpf = '123.456.789-00'",
                user_roles=["BI-AI-Developer"],
            )
        assert exc.value.pii_type == "CPF"

    def test_email_detected(self):
        from powerbi_mcp.guardrails.dlp import DLPChecker

        checker = DLPChecker(enabled=True)
        with pytest.raises(DLPError) as exc:
            checker.check_input(
                "SELECT * FROM users WHERE email = 'joao@empresa.com'",
                user_roles=["BI-AI-Developer"],
            )
        assert exc.value.pii_type == "EMAIL"

    def test_admin_bypasses_dlp(self):
        from powerbi_mcp.guardrails.dlp import DLPChecker

        checker = DLPChecker(enabled=True, bypass_roles=["BI-AI-Admin"])
        # Should not raise
        checker.check_input(
            "SELECT * FROM users WHERE cpf = '123.456.789-00'",
            user_roles=["BI-AI-Admin"],
        )

    def test_output_redaction(self):
        from powerbi_mcp.guardrails.dlp import DLPChecker

        checker = DLPChecker(enabled=True)
        data = {
            "name": "João",
            "cpf": "123.456.789-00",
            "orders": [{"id": 1, "email": "x@y.com"}],
        }
        redacted = checker.redact_output(data, user_roles=["BI-AI-Developer"])
        assert "[REDACTED:CPF]" in redacted["cpf"]
        assert "[REDACTED:EMAIL]" in redacted["orders"][0]["email"]
        assert redacted["name"] == "João"
