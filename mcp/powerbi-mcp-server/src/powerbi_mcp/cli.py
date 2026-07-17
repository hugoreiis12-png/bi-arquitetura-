"""CLI de administração para o servidor Power BI MCP.

Uso:
    powerbi-mcp-admin token issue --action deploy_test --target PR#127
    powerbi-mcp-admin token approve --token apv_xxx
    powerbi-mcp-admin user pause --user joao@empresa.com --duration 1h
    powerbi-mcp-admin audit tail --filter user=joao
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta

import structlog

from .config import get_settings
from .guardrails import ApprovalService, RateLimiter

logger = structlog.get_logger()


async def cmd_token_issue(args):
    settings = get_settings()
    approval = ApprovalService(settings.redis_url, settings.approval_token_ttl_minutes)
    try:
        from .guardrails import UserContext

        user = UserContext(
            user_id=args.user_id,
            email=args.user_id,
            roles=["BI-AI-Developer"],
        )
        required = 2 if "prod" in args.action and settings.require_two_approvers_for_prod else 1
        token = await approval.issue_token(
            user=user,
            action=args.action,
            target=args.target,
            required_approvers=required,
            metadata={"reason": args.reason or ""},
        )
        print(f"\n Token issued:")
        print(f"   Token:    {token.token}")
        print(f"   Action:   {token.action}")
        print(f"   Target:   {token.target}")
        print(f"   Required: {required} approver(s)")
        print(f"   Expires:  {token.expires_at}")
        print(f"\n   Approvers can use:")
        print(f"   powerbi-mcp-admin token approve --token {token.token}")
    finally:
        await approval.close()


async def cmd_token_approve(args):
    settings = get_settings()
    approval = ApprovalService(settings.redis_url)
    try:
        from .guardrails import UserContext

        approver = UserContext(
            user_id=args.approver_id,
            email=args.approver_id,
            roles=["BI-AI-Steward"],
        )
        token = await approval.approve(args.token, approver)
        print(f"\n Approval added.")
        print(f"   Approvers: {len(token.approvers)}/{token.required_approvers}")
        if token.has_enough_approvers():
            print(f"    Token is ready to use.")
            print(f"   Target: {token.target}, Action: {token.action}")
        else:
            print(f"    Waiting for {token.required_approvers - len(token.approvers)} more approver(s)")
    finally:
        await approval.close()


async def cmd_user_pause(args):
    settings = get_settings()
    rate_limiter = RateLimiter(settings.redis_url)
    try:
        duration = int(args.duration.replace("h", "")) * 3600 if "h" in args.duration else int(args.duration.replace("m", "")) * 60
        await rate_limiter.pause_user(args.user_id, duration)
        print(f" User {args.user_id} paused for {args.duration}")
    finally:
        await rate_limiter.close()


def main():
    parser = argparse.ArgumentParser(description="Power BI MCP admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # token
    token_p = sub.add_parser("token", help="Manage approval tokens")
    token_sub = token_p.add_subparsers(dest="subcommand", required=True)

    issue = token_sub.add_parser("issue", help="Issue a new approval token")
    issue.add_argument("--action", required=True)
    issue.add_argument("--target", required=True)
    issue.add_argument("--user-id", required=True)
    issue.add_argument("--reason", default="")

    approve = token_sub.add_parser("approve", help="Approve a token")
    approve.add_argument("--token", required=True)
    approve.add_argument("--approver-id", required=True)

    # user
    user_p = sub.add_parser("user", help="User management")
    user_sub = user_p.add_subparsers(dest="subcommand", required=True)

    pause = user_sub.add_parser("pause", help="Pause a user")
    pause.add_argument("--user-id", required=True)
    pause.add_argument("--duration", default="1h")

    args = parser.parse_args()

    if args.command == "token" and args.subcommand == "issue":
        asyncio.run(cmd_token_issue(args))
    elif args.command == "token" and args.subcommand == "approve":
        asyncio.run(cmd_token_approve(args))
    elif args.command == "user" and args.subcommand == "pause":
        asyncio.run(cmd_user_pause(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
