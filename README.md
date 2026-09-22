# Kobby Manager

Kobby Manager is a deterministic creator analytics platform for Instagram and
TikTok. It synchronizes platform data into PostgreSQL, computes evidence-based
analytics, stores observations and hypotheses, and exposes read-only tools
through Model Context Protocol (MCP).

The model-facing architecture is deliberately separate from the data system:

```text
Instagram / TikTok
        ↓ OAuth + sync
FastAPI + analytics services
        ↓
Neon PostgreSQL
        ↓
MCP read-only tools  ← ChatGPT or another MCP client
```

## Production

- Application: https://kobby-manager.vercel.app
- MCP endpoint: https://kobby-manager.vercel.app/mcp/
- Hosting: Vercel Python serverless runtime
- Database: Neon PostgreSQL
- Authentication: Clerk OAuth/JWT
- Deployment branch: `mcp-production`

The MCP endpoint is authenticated. Clients must complete OAuth/PKCE; do not
paste a bearer token or platform credential into a client configuration.

## MCP tools

The server currently exposes eight read-only tools:

| Tool | Purpose |
| --- | --- |
| `get_creator_overview` | Account totals, follower counts, and high-level intelligence |
| `get_accounts` | Connected platform accounts and follower totals |
| `get_recent_performance` | Aggregated performance for a time window |
| `get_content_themes` | Theme performance compared with platform baselines |
| `get_top_posts` | Posts ranked by views, likes, reach, shares, saves, or other metrics |
| `get_post_details` | One post's content, metrics, themes, and related evidence |
| `search_posts` | Search by caption, platform, theme, and metric thresholds |
| `get_manager_memory` | Facts, observations, hypotheses, and accumulated knowledge |

All tools are read-only and creator-scoped. Credentials and access tokens are
never returned by the tools.

## Authentication flow

1. The MCP client requests the public protected-resource metadata endpoint.
2. The endpoint identifies Clerk as the authorization server.
3. The client performs OAuth 2.1 authorization-code flow with PKCE.
4. The API validates the Clerk JWT signature, issuer, resource/audience, and
   scope.
5. The JWT subject is mapped to a creator record in PostgreSQL.
6. Every REST and MCP query is filtered to that creator.

The public discovery endpoint is:

`https://kobby-manager.vercel.app/.well-known/oauth-protected-resource`

## Repository layout

```text
app/
  main.py                 FastAPI app, CORS, MCP mount, OAuth discovery
  auth.py                 Clerk JWT validation and creator scoping
  config.py               Environment-driven settings
  database.py             Async SQLAlchemy engine and serverless-safe sessions
  api/                    REST routers and platform OAuth callbacks
  mcp/server.py           Eight MCP tools
  models/                 SQLAlchemy models
  services/
    dashboard.py          Shared analytics/query service layer
    sync.py               Platform synchronization
    analysis.py           Statistical analysis and knowledge generation
    instagram.py          Meta Graph API client
    tiktok.py             TikTok API client
    encryption.py         Fernet token encryption at rest
alembic/                  Database migrations
api/index.py              Vercel Python entry point
tests/                    Unit, integration, OAuth, MCP, and tenant tests
vercel.json               Vercel routing/build configuration
requirements.txt          Vercel runtime dependencies
```

## Local setup

Requirements: Python 3.11+, PostgreSQL or Neon, and Node.js only if using
the optional dashboard tooling.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Never commit `.env`. Generate a Fernet encryption key for local development:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Environment configuration

Set these variables in local `.env` and in Vercel's encrypted Environment
Variables. Values are intentionally absent from this repository.

| Variable group | Variables |
| --- | --- |
| Database | `DATABASE_URL`, optional `DATABASE_URL_UNPOOLED`, `NEON_BRANCH` |
| Encryption | `ENCRYPTION_KEY`, `SECRET_KEY` |
| Deployment | `BASE_URL`, `ALLOWED_ORIGINS` |
| Clerk | `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_JWKS_URL`, optional `CLERK_ISSUER` |
| MCP OAuth | optional `MCP_RESOURCE_URL`, `MCP_OAUTH_CLIENT_ID` |
| Instagram/Meta | `META_APP_ID`, `META_APP_SECRET` |
| TikTok | `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` |

## Platform connections

Instagram and TikTok are connected through the REST OAuth routes. Production
callback URLs are derived from `BASE_URL`:

```text
https://kobby-manager.vercel.app/api/auth/instagram/callback
https://kobby-manager.vercel.app/api/auth/tiktok/callback
```

The provider dashboards must allow those exact HTTPS callback URLs. Platform
tokens are encrypted with Fernet before being stored in PostgreSQL and
decrypted only when making provider API requests.

## Sync and analysis

The normal workflow is:

1. Connect a platform account through OAuth.
2. Run account synchronization to import posts and account snapshots.
3. Enrich available Instagram insights.
4. Run the analysis endpoints for account and cross-platform analysis.
5. Query the resulting data through the dashboard or MCP.

The analytics engine uses platform-specific baselines, medians, outlier
detection, content-theme classification, time evolution, and cross-platform
normalization. It distinguishes measured facts, observations, and hypotheses;
it does not claim causation from correlation alone.

## Database migrations

```bash
alembic upgrade head
```

Current migrations include the initial schema, manager decisions, OAuth
transactions for serverless OAuth state, and the Clerk creator mapping.

## Testing

```bash
pytest -q
python -m compileall -q app tests
git diff --check
```

The repository's current test suite covers MCP contracts, OAuth behavior,
encryption, tenant isolation, analytics services, schemas, and video
measurement helpers.

## Deployment

The GitHub repository deploys the `mcp-production` branch to Vercel. The
Python entry point is `api/index.py`; Vercel uses `requirements.txt` and
`vercel.json`.

Production also runs one protected account sync per day at 03:00 UTC. Vercel
Hobby permits daily cron jobs at no additional cron charge, although function
usage and third-party API quotas still apply. Instagram per-post insight
enrichment is intentionally manual because it makes one provider request per
post.

### Manual Instagram insight enrichment

After syncing an Instagram account, use the Accounts page's **Enrich
Insights** action. This requests available per-post reach, views, saves,
shares, profile visits, and follower-attribution metrics from Meta.

The API equivalent is:

```text
POST /api/accounts/{instagram_account_id}/enrich-insights
```

This can take longer than a normal sync and Meta may reject insights for older
posts or posts whose account type/API eligibility has changed. A failed insight
request does not delete the post or its existing metrics.

For a manual all-account run, use `scripts/sync_all_accounts.py` with a
short-lived Clerk JWT supplied through the shell environment:

```bash
export KOBBY_CLERK_TOKEN='your-short-lived-clerk-jwt'
python scripts/sync_all_accounts.py
```

Use `--skip-insights` when only the Instagram/TikTok account sync is needed.
Never put the token in the script or commit it.

For a manual deployment:

```bash
vercel --prod
```

After deployment, verify the public health endpoint, OAuth discovery endpoint,
and an authenticated MCP connection. Do not expose production secrets in logs,
commits, issue reports, screenshots, or documentation.

## Current data snapshot

The latest verified snapshot in the project history contained 199 synced
posts, approximately 14.4K combined followers, 84 observations, 4 hypotheses,
and 5 recommendations. That snapshot is historical; clients should call the
MCP tools for current values.

## Security notes

- Keep `.env`, provider secrets, Clerk secrets, database URLs, Fernet keys,
  and JWTs outside Git.
- Rotate any credential that has appeared in chat, shell output, screenshots,
  or an issue.
- Use separate provider and Clerk credentials for development and production.
- Keep MCP tools read-only until write-tool authorization and audit logging are
  designed and tested.
