#!/usr/bin/env python3
"""Manually sync every connected Kobby Manager account.

The script syncs both Instagram and TikTok. For Instagram it can also run
the slower per-post insight enrichment step.

Usage:
    export KOBBY_CLERK_TOKEN='your short-lived Clerk JWT'
    python scripts/sync_all_accounts.py
    python scripts/sync_all_accounts.py --skip-insights

Never commit the token or place it in this file.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx


DEFAULT_API = "https://kobby-manager.vercel.app/api"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default=os.environ.get("KOBBY_API_URL", DEFAULT_API),
        help="API base URL (default: production Kobby Manager API)",
    )
    parser.add_argument(
        "--skip-insights",
        action="store_true",
        help="Sync accounts but skip Instagram per-post insight enrichment",
    )
    args = parser.parse_args()

    token = os.environ.get("KOBBY_CLERK_TOKEN")
    if not token:
        print("Set KOBBY_CLERK_TOKEN to a valid Clerk JWT first.", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {token}"}
    api = args.api.rstrip("/")

    async with httpx.AsyncClient(
        base_url=api,
        headers=headers,
        timeout=httpx.Timeout(120.0, connect=20.0),
    ) as client:
        accounts_response = await client.get("/accounts/")
        if accounts_response.is_error:
            print(
                f"Could not list accounts ({accounts_response.status_code}): "
                f"{accounts_response.text}",
                file=sys.stderr,
            )
            return 1

        accounts = accounts_response.json()
        if not accounts:
            print("No active connected accounts found.")
            return 0

        exit_code = 0
        for account in accounts:
            account_id = account["id"]
            platform = account["platform"]
            username = account.get("username", "unknown")

            response = await client.post(f"/accounts/{account_id}/sync")
            if response.is_error:
                print(
                    f"SYNC FAILED {platform} @{username} "
                    f"({response.status_code}): {response.text}"
                )
                exit_code = 1
                continue

            print(f"SYNCED {platform} @{username}: {response.json()}")

            if platform == "instagram" and not args.skip_insights:
                insights = await client.post(
                    f"/accounts/{account_id}/enrich-insights"
                )
                if insights.is_error:
                    print(
                        f"INSIGHTS FAILED Instagram @{username} "
                        f"({insights.status_code}): {insights.text}"
                    )
                    exit_code = 1
                else:
                    print(
                        f"INSIGHTS UPDATED Instagram @{username}: "
                        f"{insights.json()}"
                    )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
