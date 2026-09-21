# Kobby Manager — Full Project Documentation

## 1. Project Overview

Kobby Manager is an AI-powered talent management system built for Kobby Cooper, a fitness and lifestyle content creator with accounts on Instagram (@kobbycooper, 13,388 followers) and TikTok (@fittokboy, 977 followers). Unlike a passive analytics dashboard, the system is designed as an active manager that observes performance data, forms hypotheses about what works, makes evidence-backed recommendations, and learns from outcomes.

The core philosophy: the first thing a user sees when they open the product is not a chart — it is "here is what is happening with your creator career, why it is happening, and what I think you should do next." Charts exist as evidence underneath the manager's reasoning, not as the product itself.

### What the System Does

- Connects to Instagram and TikTok via OAuth, imports all historical posts and metrics
- Enriches Instagram posts with detailed insights (reach, views, saves, shares, follows, profile visits)
- Runs statistical analytics: outlier detection, content clustering, posting evolution, cross-platform comparison
- Stores observations, facts, and hypotheses in a persistent knowledge base with provenance tracking
- Provides a chat interface where the creator can ask questions and receive evidence-backed answers
- Displays everything through a professional dashboard with real-time data from both platforms

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Next.js Dashboard (:3000)                    │
│  Overview · Manager Chat · Analytics · Posts · Accounts          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (fetch)
┌───────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend (:8000)                       │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐   │
│  │ Auth API │ │Posts API │ │Manager   │ │ Dashboard API     │   │
│  │(OAuth)   │ │          │ │API       │ │ (aggregates)      │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬──────────┘   │
│       │             │            │                 │              │
│  ┌────▼─────────────▼────────────▼─────────────────▼──────────┐  │
│  │                    Services Layer                           │  │
│  │  sync.py · analysis.py · orchestrator.py · briefing.py     │  │
│  │  instagram.py · tiktok.py · oauth_session.py               │  │
│  └────────────────────────┬───────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────▼───────────────────────────────────┐  │
│  │                    Agents Layer                             │  │
│  │  Manager · Growth · Content · Brand · Research · Community │  │
│  │  Business · LLM Abstraction (OpenAI Sol/Terra/Luna)        │  │
│  └────────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     PostgreSQL Database                           │
│  40+ tables: creators, accounts, posts, metrics, snapshots,      │
│  memories, recommendations, experiments, content, business       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack — Tools and Why Each Was Chosen

### 3.1 Backend Framework

**FastAPI** (Python)
- **Purpose:** HTTP API server handling all REST endpoints, OAuth callbacks, data aggregation, and AI orchestration.
- **Why FastAPI:** Native async/await support is essential because every request may involve multiple external API calls (Instagram Graph API, TikTok API, OpenAI) that should not block the server. FastAPI's automatic OpenAPI documentation (available at `/docs`) accelerated development by making every endpoint immediately testable. Pydantic integration provides request/response validation with zero boilerplate. The framework is also directly deployable to Vercel's Python Functions, which is the planned production hosting.

**Uvicorn**
- **Purpose:** ASGI server that runs the FastAPI application.
- **Why Uvicorn:** The standard production-grade ASGI server for FastAPI. Handles async concurrency efficiently with a single process for development, and can be scaled with multiple workers in production.

### 3.2 Database

**PostgreSQL**
- **Purpose:** Primary data store for all persistent state — creator profiles, platform accounts, posts, time-series metrics, AI observations, recommendations, experiments, and manager memory.
- **Why PostgreSQL:** The project treats the database as the foundation, not the AI models. AI models are swappable; the database holds years of accumulated observations, recommendation outcomes, and learning history that cannot be regenerated. PostgreSQL was chosen over lighter alternatives because: (1) it supports JSON columns for flexible schema fields like `extra`, `audience_demographics`, `audience_source`; (2) it handles time-series metric snapshots efficiently with proper indexing; (3) it supports complex analytical queries (aggregations, window functions) needed by the analytics engine; (4) async driver support via asyncpg.

**SQLAlchemy** (with async extension)
- **Purpose:** ORM layer mapping Python classes to database tables, providing type-safe query building and relationship management.
- **Why SQLAlchemy:** The project has 40+ tables with complex relationships (posts → metrics, accounts → profiles, recommendations → evidence posts). SQLAlchemy's `Mapped` type annotations catch schema errors at development time. The async extension (`sqlalchemy.ext.asyncio`) integrates with FastAPI's async request handling so database queries don't block the event loop.

**asyncpg**
- **Purpose:** PostgreSQL async driver used by SQLAlchemy's async engine.
- **Why asyncpg:** The fastest async PostgreSQL driver for Python. Required for SQLAlchemy's async mode to work with FastAPI's `async def` endpoints.

**Alembic**
- **Purpose:** Database schema migration tool that tracks and applies incremental changes to the PostgreSQL schema.
- **Why Alembic:** The schema evolves as features are added (e.g., the `manager_decisions` table was added in a second migration after the initial schema). Alembic generates migration scripts from SQLAlchemy model changes, making schema evolution reproducible and version-controlled. Two migrations exist:
  - `639cb7baf8d8_initial_schema.py` — creates all 40+ tables
  - `a1b2c3d4e5f6_add_manager_decisions.py` — adds the manager_decisions table

### 3.3 AI Provider

**OpenAI API** (sole provider as of 2026-09-09)
- **Purpose:** Powers all AI capabilities — strategic reasoning, content analysis, classification, vision analysis of video frames, and audio transcription.
- **Why OpenAI as sole provider:** Simplifies the dependency chain to one provider that covers text reasoning, vision (image/frame analysis), and transcription. The project previously used Anthropic but switched because OpenAI's current model lineup covers all required modalities through a single API key and SDK.

**Model routing by cost tier:**

| Tier | Model | Purpose |
|------|-------|---------|
| Strategy | GPT-5.6 Sol | Complex reasoning: weekly reviews, brand diagnosis, manager decisions |
| Analysis | GPT-5.6 Terra | Content scoring, experiment evaluation, visual analysis |
| Routine | GPT-5.6 Luna | Classification, comment categorisation, caption generation |
| Transcription | GPT-4o Transcribe | Speech-to-text for video audio tracks |

- **Why tiered routing:** Not every AI task requires the most expensive model. Classifying a comment's sentiment is a Luna-tier task; deciding whether to pivot Kobby's brand positioning is a Sol-tier task. This routing keeps costs proportional to task complexity.

**Model-agnostic LLM layer** (`app/agents/llm.py`)
- **Purpose:** Abstracts the AI provider behind `complete()`, `analyze_images()`, and `transcribe()` functions so that agent code never imports provider SDKs directly.
- **Why:** Providers and models change. The layer allows swapping from OpenAI to any other provider by changing config, without touching agent logic.

### 3.4 Platform Integrations

**httpx**
- **Purpose:** HTTP client for all external API calls — Instagram Graph API, TikTok Content API, and Meta OAuth endpoints.
- **Why httpx:** Async-native HTTP client that works naturally with FastAPI's async handlers. Supports timeouts, connection pooling, and streaming. Used instead of `requests` because all platform API calls happen inside `async def` functions.

**Instagram Graph API (Meta, v26.0)**
- **Purpose:** Fetches Kobby's Instagram data — media items, likes, comments, reach, views, saves, shares, follows, profile visits.
- **Why the Graph API:** The only official way to read Instagram professional account data programmatically. The project uses Facebook Login for Business (implicit grant flow) because it provides long-lived user tokens and access to `instagram_manage_insights` scope, which unlocks metrics beyond basic likes/comments.
- **Key implementation detail:** Instagram's insights API returns different metrics for Reels vs Carousels/Feed. The enrichment function (`enrich_ig_insights`) detects post type and sends format-appropriate metric requests:
  - Carousels/Feed: `reach,saved,shares,likes,comments,views,follows,profile_visits`
  - Reels: `reach,saved,shares,likes,comments,views,ig_reels_avg_watch_time,total_interactions`

**TikTok Content API (v2)**
- **Purpose:** Fetches Kobby's TikTok data — video list, view counts, likes, comments, shares, user profile.
- **Why TikTok v2 API:** The current version of TikTok's official developer API. Uses OAuth 2.0 with PKCE (Proof Key for Code Exchange) for secure desktop authorization.
- **Key implementation detail:** TikTok's PKCE implementation deviates from RFC 7636 — the code_challenge uses hex-encoded SHA-256 (`hashlib.sha256().hexdigest()`) instead of the standard base64url encoding. The video list endpoint also requires fields as query parameters, not in the JSON body.

### 3.5 OAuth and Security

**HMAC-signed state tokens** (`app/services/oauth_state.py`)
- **Purpose:** CSRF protection for OAuth flows. Each authorization URL includes a state parameter that is an HMAC signature, preventing cross-site request forgery attacks.
- **Why HMAC instead of random tokens:** HMAC signatures can be validated without database lookups — the server just re-computes the signature and compares. This is stateless and fast.

**In-memory OAuth session store** (`app/services/oauth_session.py`)
- **Purpose:** Stores temporary OAuth transaction data (provider, creator_id, PKCE code_verifier) between the authorization redirect and the callback, keyed by the HMAC state.
- **Why in-memory:** OAuth transactions are short-lived (seconds to minutes), single-use, and server-local. A database table would be unnecessary overhead. The store prunes expired entries automatically with a configurable TTL (default 600 seconds).
- **Why single-use:** `pop_oauth_session()` deletes the session on retrieval, preventing replay attacks where a callback URL is used more than once.

**Browser bridge** (Instagram callback)
- **Purpose:** Instagram's implicit grant flow returns the access token in the URL fragment (`#access_token=...`), which is never sent to the server. The bridge is a minimal HTML page served at `/api/auth/instagram/callback` that runs JavaScript to read the fragment and POST the token to a server endpoint.
- **Why a bridge:** This is the only way to capture implicit grant tokens server-side. Meta requires `response_type=token` for Facebook Login for Business, which means the token arrives in the fragment, not as a query parameter.

**python-jose / passlib**
- **Purpose:** JWT token generation and password hashing for future user authentication.
- **Why:** Standard libraries for secure authentication. Not yet actively used in the OAuth flows (which use platform tokens directly) but included for when multi-user support is added.

### 3.6 Analytics Engine

**Custom statistical analysis** (`app/services/analysis.py`)
- **Purpose:** The core intelligence layer that transforms raw metrics into actionable observations.
- **Why custom instead of a library:** The analytics are domain-specific to creator content management. Generic analytics libraries would need extensive configuration to handle the specific patterns this system detects:

  - **IQR-based outlier detection:** Identifies statistically anomalous posts (like the 634K-view TikTok breakout that represents 90.6% of lifetime views) and computes baselines both with and without outliers.
  - **Content clustering:** Maps posts to 8 content theme clusters (calisthenics, workout_routine, physique, lifestyle, motivation, trend_viral, military_outdoor, collaboration) using keyword matching on captions. Computes per-cluster performance relative to the account median.
  - **Posting evolution:** Tracks how metrics change over time by grouping posts into quarterly periods.
  - **Cross-platform comparison:** Compares content themes across Instagram and TikTok using relative performance (each metric normalized to its platform's own median) so that raw metric differences between platforms don't skew the comparison.
  - **Idempotent observation storage:** The `_obs` helper prevents duplicate observations on re-runs by checking for 70% evidence overlap with existing memories of the same category and knowledge type. It updates instead of duplicating.

**Knowledge type system:**
- **FACT:** Measured data that is objectively true (e.g., "TikTok account has 81 videos, 977 followers")
- **OBSERVATION:** Pattern derived from data analysis (e.g., "Lifestyle content outperforms baseline by 1.8x")
- **HYPOTHESIS:** Conjecture that needs more evidence (e.g., "Kobby's strongest positioning may be personality/lifestyle-led rather than calisthenics-led")

### 3.7 Agent System

**6 specialist agents + Manager orchestrator** (`app/agents/`)
- **Purpose:** Each agent has domain expertise and a specific system prompt. The Manager Agent routes incoming requests to the appropriate specialists, gathers their responses, and synthesizes a unified answer.

| Agent | Responsibility |
|-------|---------------|
| Manager | Orchestrates other agents, makes final decisions, generates briefs |
| Growth | Follower growth strategy, distribution analysis, posting time optimization |
| Content | Content ideas, scripts, hooks, series concepts, caption writing |
| Brand | Brand positioning, profile optimization, visual identity, niche strategy |
| Research | Competitor analysis, trend detection, external intelligence |
| Community | Comment management, follower relationships, engagement |
| Business | Sponsorship evaluation, revenue strategy, monetisation readiness |

**BaseAgent** (`app/agents/base.py`)
- **Purpose:** Abstract base class providing `run()`, `run_json()`, and `run_validated()` methods. Agents inherit from this and only need to define their system prompt and default cost tier.
- **Why a base class:** Eliminates boilerplate. Every agent uses the same LLM calling pattern — construct system prompt + context, send messages, parse response. The `run_validated()` method adds Pydantic schema validation on top, ensuring structured outputs conform to expected shapes.

**Orchestrator** (`app/services/orchestrator.py`)
- **Purpose:** Full pipeline for handling user requests: classify intent → route to specialist agents → parallel dispatch → evidence validation → conflict detection → synthesis → record decision.
- **Why a pipeline:** A user question like "what should I post tomorrow?" touches growth strategy, content creation, and brand positioning simultaneously. The orchestrator dispatches to multiple agents in parallel, then merges their recommendations into a single coherent response with provenance.

### 3.8 Frontend Dashboard

**Next.js 16** (App Router, TypeScript)
- **Purpose:** The user-facing dashboard that displays all data and provides the manager chat interface.
- **Why Next.js:** Server-side rendering for fast initial loads, file-system routing for clean page organization, and direct deployment to Vercel. The App Router pattern (layout.tsx wrapping page.tsx) provides shared layout (sidebar) across all pages without re-rendering on navigation.

**TypeScript**
- **Purpose:** Type safety across all frontend code — API response shapes, component props, state management.
- **Why TypeScript:** The API returns complex nested objects (posts with metrics, observations with evidence). TypeScript catches shape mismatches at compile time instead of at runtime in the browser.

**Tailwind CSS v4**
- **Purpose:** Utility-first styling for all dashboard components.
- **Why Tailwind:** Enables rapid UI development without writing custom CSS files. The v4 release uses CSS-based configuration via `@theme inline {}` blocks in `globals.css` instead of a JavaScript config file, which is cleaner. Custom theme colors (sidebar-bg, accent, positive, negative, warning, platform-specific colors) are defined as CSS custom properties.

**Recharts**
- **Purpose:** Renders the performance timeline chart on the Overview and Analytics pages — dual-platform area chart showing monthly average likes/reach/views over time.
- **Why Recharts:** React-native charting library that works with JSX composition. The `AreaChart` with gradient fills and dual data series (Instagram pink, TikTok indigo) provides a clean visual that matches the dashboard aesthetic. Responsive container automatically handles window resizing.

**TanStack React Query** (@tanstack/react-query)
- **Purpose:** Client-side data fetching, caching, and state management for all API calls.
- **Why React Query:** Every dashboard page needs data from the FastAPI backend. React Query provides: (1) automatic caching with configurable stale time (30 seconds), so navigating between pages doesn't re-fetch; (2) loading/error states without manual `useState` management; (3) `useMutation` for sync/analyze actions with automatic cache invalidation; (4) background refetching when the window regains focus (disabled for this app to reduce API load).

**Lucide React**
- **Purpose:** Icon library providing all sidebar and UI icons (LayoutDashboard, MessageSquare, BarChart3, ArrowUp, ArrowDown, Sparkles, etc.).
- **Why Lucide:** Tree-shakeable (only imports the icons actually used), consistent visual style, and React-native (each icon is a component that accepts size and className props).

### 3.9 Dashboard Pages

| Page | Purpose |
|------|---------|
| **Overview** (`/`) | Greeting, chat bar, follower stat cards (IG/TT/Total), manager brief (top observations + hypotheses), performance chart, content winners, top posts |
| **Manager** (`/manager`) | Chat interface with suggested starter prompts, message bubbles, evidence display, loading animation |
| **Analytics** (`/analytics`) | Performance chart, content winners, knowledge base counts (Facts/Observations/Hypotheses), full observation list with confidence and sample size |
| **Posts** (`/posts`) | Sortable table of all 198 posts with platform filter (All/Instagram/TikTok), columns for reach, views, likes, saves, shares |
| **Accounts** (`/accounts`) | Connected account cards with sync buttons, platform links, last sync result display |
| **Experiments** (`/experiments`) | Placeholder — will show A/B content experiments |
| **Audience** (`/audience`) | Placeholder — will show follower demographics |
| **Opportunities** (`/opportunities`) | Placeholder — will show brand deals and monetisation |
| **Calendar** (`/calendar`) | Placeholder — will show content planning calendar |
| **Settings** (`/settings`) | Manager autonomy level, auto-approve toggles, AI provider info |

### 3.10 Development and Quality Tools

**Ruff**
- **Purpose:** Python linter and formatter.
- **Why Ruff:** Extremely fast (Rust-based), replaces both flake8 and black, configured in pyproject.toml.

**mypy**
- **Purpose:** Static type checking for Python code.
- **Why mypy:** Catches type errors in the complex data transformations between API responses, ORM models, and agent outputs.

**pytest / pytest-asyncio**
- **Purpose:** Test framework supporting async test functions.
- **Why:** Tests exist for OAuth session behavior (single-use, TTL expiry). pytest-asyncio allows testing async service functions directly.

**ESLint / eslint-config-next**
- **Purpose:** JavaScript/TypeScript linting for the dashboard code.
- **Why:** Catches React anti-patterns, accessibility issues, and Next.js-specific problems (missing Image imports, etc.).

### 3.11 Background Processing (Planned)

**Celery + Redis**
- **Purpose:** Async task queue for long-running operations (full account sync, batch analysis, video processing).
- **Why Celery:** Some operations (syncing 117 posts with individual API calls, running analysis across all posts) take 30+ seconds and shouldn't block HTTP requests. Celery workers process these in the background. Redis serves as both the message broker and result backend.
- **Current status:** Dependencies installed, task directory exists but is empty. Currently all operations run synchronously within HTTP request handlers.

### 3.12 Video Analysis (Planned)

**FFmpeg / ffmpeg-python**
- **Purpose:** Extract frames from video files for visual analysis, extract audio tracks for transcription, measure video properties (duration, resolution, bitrate).
- **Why FFmpeg:** Industry-standard tool for video processing. The Python wrapper provides a clean API for building FFmpeg command pipelines.

**Whisper (whisper-timestamped)**
- **Purpose:** Local speech-to-text transcription with word-level timestamps.
- **Why Whisper:** Can run locally without API calls for development/testing. The timestamped variant provides word-level timing which enables hook analysis (what's said in the first 3 seconds) and pacing analysis.

**Pillow (PIL)**
- **Purpose:** Image processing for extracted video frames — resizing, format conversion, thumbnail generation.
- **Why Pillow:** Standard Python imaging library needed for preparing frames before sending to the OpenAI vision API.

---

## 4. Database Schema Overview

The database contains 40+ tables organized across 7 model modules:

### Core Models (`app/models/core.py`)
- **Creator** — The person being managed (id, name)
- **PlatformAccount** — Connected social accounts (platform, username, access_token, refresh_token)
- **ProfileSnapshot** — Periodic captures of profile state (followers, bio, profile pic) for tracking changes over time
- **Post** — Every piece of content across all platforms (caption, hashtags, type, published_at, objective)
- **PostMetric** — Time-series metrics for each post (views, likes, comments, shares, saves, reach, impressions, followers_from_post, profile_visits, avg_watch_time, retention_rate, completion_rate, audience_source, audience_demographics)
- **AccountMetricSnapshot** — Daily account-level metrics (followers, reach, impressions, profile_visits, audience data)

### Manager Models (`app/models/manager.py`)
- **ManagerMemory** — The AI's persistent knowledge base (knowledge_type: FACT/OBSERVATION/HYPOTHESIS, statement, evidence_post_ids, confidence, sample_size)
- **Recommendation** — Manager-generated advice with provenance (summary, reasoning, evidence, confidence, priority, user_decision, outcome_verdict, manager_score)
- **DailyBrief** — Generated daily summaries (account_status, key_observation, actions, warnings, opportunities)
- **WeeklyReview** — Weekly analysis (what_worked, what_failed, stop/start/continue, next_week_strategy)
- **ManagerDecision** — Audit log of every decision the manager makes
- **ManagerConfig** — Autonomy settings (auto-approve levels for reads, analytics, drafts, profile changes, posts)

### Content Models (`app/models/content.py`)
- **ContentIdea** — Generated content concepts with scores
- **ContentCalendar** — Scheduled content pipeline
- **ContentSeries** — Recurring content series
- **Hook** — Opening hooks for videos
- **Transcript** — Video transcriptions with timestamps
- **VideoVisualFeatures** — Visual analysis results (scene types, face visibility, motion)
- **DraftReview** — AI feedback on draft videos before posting

### Analytics Models (`app/models/analytics.py`)
- **Experiment** — A/B content experiments with variants and outcomes
- **PostingTimeAnalysis** — Optimal posting time analysis
- **GrowthLoop** — Identified growth feedback loops
- **ObjectivePortfolio** — Content objective balance tracking

### Brand Models (`app/models/brand.py`)
- **BrandStrategy** — Overall brand positioning
- **ProfileScore** — Bio/grid/highlights scoring
- **PinRecommendation** — Which posts to pin

### Business Models (`app/models/business.py`)
- **Sponsorship, Revenue, Opportunity** — Business/monetisation tracking

### Community Models (`app/models/community.py`)
- **Comment, Contact, CollaborationProposal** — Community management

---

## 5. Data Flow

### Platform Connection Flow
```
User clicks "Connect Instagram"
  → GET /api/auth/instagram/connect
  → Server generates HMAC state + stores OAuth session
  → User redirected to Facebook Login
  → User authorizes
  → Redirected to /api/auth/instagram/callback (browser bridge)
  → Bridge JavaScript reads #fragment token
  → POSTs token + state to /api/auth/instagram/complete
  → Server validates state, pops OAuth session
  → Calls Meta Graph API: /me → /me/accounts → find IG account → fetch profile
  → Upserts PlatformAccount in database
  → Returns success to browser bridge → "Instagram connected: @kobbycooper"
```

### Data Sync Flow
```
POST /api/accounts/4/sync
  → sync_instagram_account(4)
  → Fetch IG profile via Graph API
  → Paginated fetch of all media (follows paging.next URLs)
  → For each media item:
    → Upsert Post record
    → Create PostMetric snapshot (likes, comments from basic API)
  → Create ProfileSnapshot
  → Create AccountMetricSnapshot (daily follower count)
  → Return summary: {media_fetched: 117, posts_created: 117, ...}
```

### Insights Enrichment Flow
```
POST /api/accounts/4/enrich-insights
  → For each post without reach data:
    → Detect post type (Reel vs Carousel/Feed)
    → Call /insights with format-appropriate metrics
    → Update existing PostMetric row with reach, views, saves, shares, etc.
    → 0.3s delay between requests (rate limiting)
  → Return: {enriched: 66, failed: 51, skipped: 0}
  (51 failures = pre-business-account-conversion posts, Meta limitation)
```

### Analytics Flow
```
POST /api/manager/analyze/full/3  (TikTok)
  → Load all posts + latest metrics for account
  → IQR outlier detection → identify 634K-view breakout
  → Compute baselines with and without outliers
  → Content clustering → map posts to 8 theme clusters
  → Compare each cluster's median to account median
  → Quarterly evolution analysis
  → Repeatability analysis (which themes are consistent)
  → Store observations idempotently (70% evidence overlap check)
  → Return full analytics report
```

---

## 6. Current State

### Connected Accounts
| Platform | Username | Followers | Posts | Insights |
|----------|----------|-----------|-------|----------|
| TikTok | @fittokboy | 977 | 81 | Views, likes, shares, comments |
| Instagram | @kobbycooper | 13,388 | 117 | 66 posts with full insights (reach, views, saves, shares, follows, profile visits) |

### Knowledge Base
- 8 FACTs (measured data points)
- 18+ OBSERVATIONs (data-derived patterns)
- 4+ HYPOTHESEs (including the brand positioning hypothesis at 0.45 confidence)

### Key Finding
Lifestyle content is the only cross-platform winner — outperforming the baseline on both TikTok (1.77x) and Instagram (1.44x). The 634K-view TikTok breakout represents 90.6% of lifetime views and is correctly identified as a statistical outlier excluded from baseline calculations.

---

## 7. File Structure

```
kobby-manager/
├── app/                          # FastAPI backend
│   ├── main.py                   # App entry point, CORS, router registration
│   ├── config.py                 # Pydantic Settings from .env
│   ├── database.py               # Async SQLAlchemy engine + session
│   ├── agents/                   # AI agent system
│   │   ├── base.py               # BaseAgent ABC
│   │   ├── llm.py                # Model-agnostic LLM layer
│   │   ├── manager.py            # Manager orchestrator agent
│   │   ├── growth.py             # Growth strategy agent
│   │   ├── content.py            # Content creation agent
│   │   ├── brand.py              # Brand positioning agent
│   │   ├── research.py           # External intelligence agent
│   │   ├── community.py          # Community management agent
│   │   └── business.py           # Monetisation agent
│   ├── api/                      # REST endpoints
│   │   ├── auth.py               # OAuth flows (Instagram + TikTok)
│   │   ├── accounts.py           # Account CRUD, sync, insights enrichment
│   │   ├── posts.py              # Post listing, detail, draft review
│   │   ├── analytics.py          # Metrics queries, experiments
│   │   ├── manager.py            # Briefs, chat, recommendations, memory
│   │   ├── dashboard.py          # Aggregate endpoints for frontend
│   │   ├── content.py            # Ideas, calendar, series, hooks
│   │   └── brand.py              # Strategy, profile scores, pins
│   ├── models/                   # SQLAlchemy ORM models
│   │   ├── core.py               # Creator, Account, Post, Metrics
│   │   ├── manager.py            # Memory, Recommendations, Briefs
│   │   ├── content.py            # Ideas, Calendar, Hooks, Transcripts
│   │   ├── analytics.py          # Experiments, Growth Loops
│   │   ├── brand.py              # Strategy, Profile Scores
│   │   ├── business.py           # Sponsorships, Revenue
│   │   ├── community.py          # Comments, Contacts
│   │   └── intelligence.py       # Competitors, Trends
│   ├── schemas/                  # Pydantic output schemas
│   ├── services/                 # Business logic
│   │   ├── sync.py               # Platform data sync + insights enrichment
│   │   ├── analysis.py           # Analytics engine (outliers, clustering, evolution)
│   │   ├── orchestrator.py       # Multi-agent orchestration pipeline
│   │   ├── briefing.py           # Daily/weekly brief generation
│   │   ├── instagram.py          # Meta Graph API client
│   │   ├── tiktok.py             # TikTok v2 API client
│   │   ├── oauth_session.py      # In-memory OAuth store
│   │   ├── oauth_state.py        # HMAC state token generation
│   │   ├── video_analyzer.py     # Video analysis pipeline
│   │   └── _whisper_cache.py     # Whisper model singleton
│   └── tasks/                    # Celery tasks (planned)
├── dashboard/                    # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx        # Root layout with sidebar
│   │   │   ├── page.tsx          # Overview page
│   │   │   ├── providers.tsx     # React Query provider
│   │   │   ├── globals.css       # Tailwind v4 theme
│   │   │   ├── manager/page.tsx  # Manager chat
│   │   │   ├── analytics/page.tsx
│   │   │   ├── posts/page.tsx
│   │   │   ├── accounts/page.tsx
│   │   │   ├── experiments/page.tsx
│   │   │   ├── audience/page.tsx
│   │   │   ├── opportunities/page.tsx
│   │   │   ├── calendar/page.tsx
│   │   │   └── settings/page.tsx
│   │   ├── components/
│   │   │   ├── sidebar.tsx
│   │   │   ├── stat-card.tsx
│   │   │   ├── performance-chart.tsx
│   │   │   ├── content-winners.tsx
│   │   │   ├── manager-brief.tsx
│   │   │   └── top-posts.tsx
│   │   └── lib/
│   │       └── api.ts            # API client + TypeScript interfaces
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.ts
├── frontend/                     # Public compliance site
│   └── app/
│       ├── page.js               # Landing page
│       ├── privacy/page.js       # Privacy policy
│       └── terms/page.js         # Terms of service
├── alembic/                      # Database migrations
│   └── versions/
│       ├── 639cb7baf8d8_initial_schema.py
│       └── a1b2c3d4e5f6_add_manager_decisions.py
├── tests/
│   └── test_oauth_session.py     # OAuth session tests
├── scripts/                      # Utility scripts
├── .env                          # Environment variables (gitignored)
├── .gitignore
├── pyproject.toml                # Python project config + dependencies
└── alembic.ini                   # Alembic config
```

---

## 8. Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection for Celery |
| `STRATEGY_PROVIDER` / `STRATEGY_MODEL` | AI model for complex reasoning (openai / gpt-5.6-sol) |
| `ANALYSIS_PROVIDER` / `ANALYSIS_MODEL` | AI model for content analysis (openai / gpt-5.6-terra) |
| `ROUTINE_PROVIDER` / `ROUTINE_MODEL` | AI model for classification (openai / gpt-5.6-luna) |
| `VISION_PROVIDER` / `VISION_MODEL` | AI model for image analysis (openai / gpt-5.6-terra) |
| `TRANSCRIBE_MODEL` | Audio transcription model (gpt-4o-transcribe) |
| `OPENAI_API_KEY` | OpenAI API authentication |
| `META_APP_ID` / `META_APP_SECRET` | Facebook/Instagram app credentials |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | TikTok sandbox app credentials |
| `SECRET_KEY` | HMAC signing key for OAuth state tokens |

---

## 9. Running the Project

```bash
# Start PostgreSQL
sudo service postgresql start

# Apply database migrations
cd /home/kali/kobby-manager
source .venv/bin/activate
alembic upgrade head

# Start FastAPI backend (port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Start Next.js dashboard (port 3000) — in a separate terminal
cd dashboard
npm run dev
```

The dashboard is then accessible at `http://localhost:3000` and the API at `http://localhost:8000/docs`.
