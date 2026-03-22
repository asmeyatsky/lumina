# LUMINA

**The AI Visibility Platform — Be the answer.**

LUMINA is a closed-loop intelligence platform for Generative Engine Optimisation (GEO). It measures, diagnoses, optimises, and defends brand visibility across AI answer engines — Claude, GPT-4o, Gemini, and Perplexity.

Built on hexagonal architecture with DDD, MCP-native integration, and parallelism-first design.

Part of the [SYNTHERA](https://smeyatskylabs.com) platform portfolio by Smeyatsky Labs.

![LUMINA Architecture](docs/assets/architecture.jpg)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│   FastAPI REST API  ·  React Dashboard  ·  MCP Client Interfaces    │
├─────────────────────────────────────────────────────────────────────┤
│                        APPLICATION LAYER                            │
│            Use Cases  ·  Commands  ·  Queries  ·  DTOs              │
│                   DAG Orchestration (Parallel)                      │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────────┤
│  PULSE   │  GRAPH   │   BEAM   │  SIGNAL  │ INTELLI- │    ORBIT     │
│ Monitor  │ Entity   │ Content  │ Distrib  │ GENCE    │  Autonomous  │
│ & Cite   │ Intel    │ Optimise │ & Amplif │ AVS+Rec  │    Agent     │
├──────────┴──────────┴──────────┴──────────┴──────────┴──────────────┤
│                        DOMAIN LAYER                                 │
│  Entities (frozen)  ·  Value Objects  ·  Domain Events  ·  Ports    │
├─────────────────────────────────────────────────────────────────────┤
│                      INFRASTRUCTURE LAYER                           │
│  PostgreSQL  ·  Neo4j  ·  Pinecone  ·  AI Engine Adapters          │
│  MCP Servers  ·  Alerting  ·  CMS  ·  Integrations                 │
│  Claude Agent Engine  ·  Module Bridge                              │
└─────────────────────────────────────────────────────────────────────┘
```

### The Closed Loop

```
PULSE monitors AI outputs  →  GRAPH identifies entity gaps
BEAM optimises content     →  SIGNAL distributes to citation surfaces
Intelligence Engine measures improvement and recycles into PULSE

ORBIT autonomously orchestrates the entire loop — planning, executing,
and synthesising across all modules in observe-plan-act-synthesize cycles.
```

---

## Modules

### PULSE — AI Monitoring & Citation Intelligence

Continuous, multi-engine monitoring with structured citation extraction.

- Parallel query orchestration across Claude, GPT-4o, Gemini, Perplexity
- Prompt battery management with pre-built libraries by vertical
- Citation extraction (position, sentiment, accuracy, recommendations)
- Competitor share-of-voice benchmarking
- Real-time alerting (Slack, email, webhooks)

### GRAPH — Entity Intelligence & Knowledge Architecture

Models the semantic entity landscape that makes a brand citable.

- Entity profile authoring across 8 dimensions (identity, products, people, topic authority, achievements, relationships, competitive position, temporal data)
- Schema.org / JSON-LD generation
- Wikidata alignment and gap analysis
- Competitor entity benchmarking
- Relationship graph with health scoring

### BEAM — Content Optimisation for AI Retrieval

Scores and rewrites content for LLM retrieval survivability.

- 6-factor GEO scoring (entity density, answer shape, fact citability, RAG survivability, semantic authority, freshness)
- RAG simulation pipeline (semantic chunking, embedding, retrieval)
- AI-powered rewrite suggestions
- Bulk content estate auditing
- Before/after scoring

### SIGNAL — Distribution & Amplification Engine

Distributes entity and content signals to surfaces LLMs train on.

- Distribution surface mapping weighted by LLM training affinity
- Structured data submission (Google Search Console, Bing)
- Wikidata contribution workflows
- PR brief generation
- Community engagement playbooks
- Coverage tracking with citation correlation

### Intelligence Engine — Unified Scoring

Synthesises signals from all modules into a single actionable view.

- AI Visibility Score (AVS): 0-100 composite metric
  - Citation Frequency (30%) + Entity Depth (25%) + Content GEO (25%) + Distribution Coverage (20%)
- Automated root cause analysis on AVS changes
- Prioritised recommendation queue (impact/effort ratio)
- Trend analysis and predictive modelling

### Agency — White-Label Multi-Client Management

Manages GEO across a client portfolio with branded reporting.

- Multi-client dashboard with portfolio analytics
- White-label configuration (logo, colors, custom domain)
- Branded PDF report generation (weekly, monthly, quarterly)
- At-risk client detection
- Plan tier enforcement (Starter: 5 clients, Professional: 25, Unlimited)

### ORBIT — Autonomous AI Visibility Agent

Orchestrated Real-time Brand Intelligence & Transformation. A Claude-powered autonomous agent that uses all other LUMINA modules as tools to run closed-loop visibility optimisation.

- **Observe-plan-act-synthesize cycles** — the agent monitors brand state, plans corrective actions, executes them across modules, and synthesises findings into actionable insights
- **Three autonomy levels** — Supervised (approve every action), Guided (approve plan, auto-execute), Autonomous (full auto within guardrails)
- **Guardrail system** — configurable safety constraints (max cycles, max actions, allowed/blocked modules and tools) enforced before every action
- **Plan validation** — DAG-based execution plans with dependency resolution and circular dependency detection
- **Claude reasoning engine** — uses the Anthropic SDK with tool-use to plan, decide, synthesise, and evaluate goal completion
- **Module bridge** — routes agent tool calls to all 6 LUMINA modules (21 tools) through a unified interface
- **Insight aggregation** — ranked findings by severity and confidence, grouped by source module
- **Natural language goals** — e.g., *"Diagnose why our GPT-4o citation rate dropped 15% this week"*
- **Session lifecycle** — start, pause, resume, approve, complete, fail — fully tracked with domain events

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic |
| Frontend | React 19, TypeScript, Tailwind CSS, Vite, Recharts, TanStack Query |
| Database | PostgreSQL 16 (SQLAlchemy async + Alembic), Neo4j, Pinecone |
| Cache | Redis |
| AI Engines | Anthropic Claude, OpenAI GPT-4o, Google Gemini, Perplexity |
| MCP | 7 MCP servers (one per bounded context) |
| NLP | Claude-powered citation extraction, tiktoken tokenisation, OpenAI embeddings |
| Auth | JWT (PyJWT), OAuth 2.0, RBAC (4 roles, 6 permissions) |
| Integrations | Slack, SendGrid, HubSpot, Salesforce, WordPress, Webflow |
| Infrastructure | GCP Cloud Run, Cloud SQL, Artifact Registry, Secret Manager, Terraform |
| CI/CD | GitHub Actions, Docker (multi-stage), Cloud Build |

---

## Project Structure

```
lumina/
├── src/lumina/
│   ├── shared/              # Shared kernel (events, value objects, ports)
│   │   ├── domain/          # DomainEvent, BrandId, TenantId, Score, AIEngine
│   │   └── ports/           # AIEnginePort, EventBusPort, RepositoryPort
│   ├── pulse/               # AI Monitoring bounded context
│   │   ├── domain/          # MonitoringRun, Citation, PromptBattery
│   │   ├── application/     # RunMonitoringCommand, MultiEngineQueryOrchestrator
│   │   └── infrastructure/  # Claude/OpenAI/Gemini/Perplexity adapters, MCP server
│   ├── graph/               # Entity Intelligence bounded context
│   │   ├── domain/          # EntityProfile, EntityDimension, KnowledgeGap
│   │   ├── application/     # CreateEntityProfile, RunGapAnalysis, GenerateJsonLd
│   │   └── infrastructure/  # Neo4j adapter, Wikidata adapter, MCP server
│   ├── beam/                # Content Optimisation bounded context
│   │   ├── domain/          # ContentAsset, GEOScore, RAGSimulationResult
│   │   ├── application/     # ScoreContent, BulkAudit, ContentScoringPipeline
│   │   └── infrastructure/  # Web crawler, Pinecone adapter, MCP server
│   ├── signal/              # Distribution bounded context
│   │   ├── domain/          # DistributionPlan, CitationSurface, PRBrief
│   │   ├── application/     # CreateDistributionPlan, ExecuteAction
│   │   └── infrastructure/  # Search Console, Wikidata submission, MCP server
│   ├── intelligence/        # Intelligence Engine bounded context
│   │   ├── domain/          # AIVisibilityScore, Recommendation, RootCauseAnalysis
│   │   ├── application/     # CalculateAVS, GenerateRecommendations
│   │   └── infrastructure/  # MCP server
│   ├── orbit/               # Autonomous Agent bounded context
│   │   ├── domain/          # AgentSession, AgentPlan, ExecutionCycle, AgentInsight
│   │   ├── application/     # StartSession, RunCycle, RunFullSession, ApproveAction
│   │   └── infrastructure/  # Claude agent engine, Module bridge, MCP server
│   ├── agency/              # Agency white-label bounded context
│   │   ├── domain/          # Agency, ClientBrand, WhiteLabelConfig, ClientReport
│   │   ├── application/     # OnboardClient, GenerateClientReport, BulkReports
│   │   └── infrastructure/  # Report exporter, MCP server
│   ├── infrastructure/      # Cross-cutting infrastructure
│   │   ├── auth/            # JWT, RBAC, OAuth 2.0, API keys
│   │   ├── database/        # SQLAlchemy models, PostgreSQL repositories
│   │   ├── nlp/             # ML citation extraction, sentiment, entity recognition
│   │   ├── rag/             # Chunking, embeddings, retrieval simulation
│   │   ├── alerting/        # Slack, email, webhook dispatching
│   │   ├── cms/             # WordPress, Webflow, sitemap parsing
│   │   ├── integrations/    # HubSpot, Salesforce, Slack app
│   │   └── prompt_library/  # 132 templates across 5 verticals
│   └── presentation/
│       ├── api/             # FastAPI routes, middleware, schemas
│       └── config/          # Dependency injection, MCP registry
├── frontend/                # React + TypeScript + Tailwind dashboard
│   └── src/
│       ├── api/             # API client
│       ├── components/      # Layout, ScoreGauge, TrendChart, DataTable
│       ├── hooks/           # React Query hooks
│       ├── pages/           # Dashboard, PULSE, GRAPH, BEAM, SIGNAL, Intelligence
│       └── types/           # TypeScript interfaces
├── tests/                   # 697 tests across 10 modules
├── migrations/              # Alembic (21 tables, 13 enum types)
├── deploy/                  # Cloud Run, Terraform, Cloud Build
└── .github/workflows/       # CI + Deploy pipelines
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker & Docker Compose
- PostgreSQL 16 (or use Docker)

### Quick Start

```bash
# Clone
git clone https://github.com/asmeyatsky/lumina.git
cd lumina

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Start with Docker (recommended)
make dev

# Or run locally:
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run database migrations
make migrate

# Start backend
uvicorn lumina.presentation.api.app:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://lumina:lumina@localhost:5432/lumina

# Auth
JWT_SECRET=your-secret-key

# AI Engine API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_AI_API_KEY=...
PERPLEXITY_API_KEY=pplx-...

# Infrastructure (optional)
NEO4J_URI=bolt://localhost:7687
PINECONE_API_KEY=...
REDIS_URL=redis://localhost:6379

# Integrations (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
SENDGRID_API_KEY=SG....
```

---

## API

Base URL: `http://localhost:8000/api/v1`

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns JWT tokens |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/auth/me` | Current user info |

### PULSE
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/pulse/monitoring-runs` | Trigger monitoring run |
| GET | `/pulse/monitoring-runs/{run_id}` | Get run details |
| POST | `/pulse/batteries` | Create prompt battery |
| GET | `/pulse/brands/{brand_id}/trends` | Citation trends |
| GET | `/pulse/brands/{brand_id}/share-of-voice` | Share of voice |

### GRAPH
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/graph/profiles` | Create entity profile |
| GET | `/graph/profiles/{brand_id}` | Get entity profile |
| PUT | `/graph/profiles/{brand_id}/dimensions/{dim_id}` | Update dimension |
| POST | `/graph/profiles/{brand_id}/gap-analysis` | Run gap analysis |
| GET | `/graph/profiles/{brand_id}/gaps` | Get knowledge gaps |
| POST | `/graph/profiles/{brand_id}/json-ld` | Generate JSON-LD |

### BEAM
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/beam/score` | Score content by URL |
| POST | `/beam/bulk-audit` | Bulk audit URLs |
| GET | `/beam/assets/{asset_id}/score` | Get GEO score |
| POST | `/beam/assets/{asset_id}/rag-simulation` | Run RAG simulation |
| POST | `/beam/assets/{asset_id}/rewrites` | Generate rewrite suggestions |
| GET | `/beam/brands/{brand_id}/audit-summary` | Audit summary |

### SIGNAL
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/signal/plans` | Create distribution plan |
| GET | `/signal/plans/{plan_id}` | Get plan status |
| POST | `/signal/plans/{plan_id}/actions/{action_id}/execute` | Execute action |
| GET | `/signal/brands/{brand_id}/coverage` | Distribution coverage |
| POST | `/signal/brands/{brand_id}/pr-briefs` | Generate PR brief |

### Intelligence Engine
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/intelligence/brands/{brand_id}/avs` | Calculate AVS |
| GET | `/intelligence/brands/{brand_id}/avs` | Get current AVS |
| GET | `/intelligence/brands/{brand_id}/avs/trends` | AVS trends |
| GET | `/intelligence/brands/{brand_id}/recommendations` | Recommendation queue |
| POST | `/intelligence/brands/{brand_id}/root-cause` | Root cause analysis |

### Agency
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/agency` | Create agency |
| GET | `/agency/portfolio` | Portfolio overview |
| POST | `/agency/clients` | Onboard client |
| GET | `/agency/clients` | List clients |
| PUT | `/agency/white-label` | Configure branding |
| POST | `/agency/clients/{id}/reports` | Generate report |
| POST | `/agency/reports/bulk` | Bulk report generation |

### ORBIT
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orbit/sessions` | Start autonomous session |
| GET | `/orbit/sessions/{id}` | Get session state |
| POST | `/orbit/sessions/{id}/cycle` | Run one observe-plan-act-synthesize cycle |
| POST | `/orbit/sessions/{id}/run` | Run full autonomous loop to completion |
| POST | `/orbit/sessions/{id}/approve` | Approve agent's plan |
| POST | `/orbit/sessions/{id}/pause` | Pause active session |
| POST | `/orbit/sessions/{id}/resume` | Resume paused session |
| GET | `/orbit/sessions/{id}/insights` | Get ranked insights |
| GET | `/orbit/sessions/{id}/metrics` | Get session metrics |
| GET | `/orbit/brands/{brand_id}/active` | Get active session for brand |
| GET | `/orbit/brands/{brand_id}/history` | Get session history |

### Integrations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/integrations` | List configured integrations |
| POST | `/integrations` | Configure integration |
| POST | `/integrations/{id}/test` | Test connection |
| POST | `/integrations/{id}/sync` | Trigger sync |

---

## MCP Servers

LUMINA exposes 7 MCP servers, one per bounded context:

| Server | Tools | Resources |
|--------|-------|-----------|
| `lumina-pulse` | `run_monitoring`, `create_prompt_battery` | `pulse://runs/{id}`, `pulse://brands/{id}/trends` |
| `lumina-graph` | `create_entity_profile`, `update_dimension`, `run_gap_analysis`, `generate_json_ld` | `graph://profiles/{id}`, `graph://gaps/{id}` |
| `lumina-beam` | `score_content`, `run_rag_simulation`, `generate_rewrites`, `bulk_audit` | `beam://assets/{id}/score`, `beam://brands/{id}/audit-summary` |
| `lumina-signal` | `create_distribution_plan`, `execute_action`, `generate_pr_brief`, `map_surfaces` | `signal://brands/{id}/coverage`, `signal://plans/{id}` |
| `lumina-intelligence` | `calculate_avs`, `run_root_cause_analysis`, `generate_recommendations` | `intelligence://brands/{id}/avs`, `intelligence://brands/{id}/recommendations` |
| `lumina-agency` | `onboard_client`, `configure_white_label`, `generate_report`, `bulk_generate_reports` | `agency://portfolio`, `agency://clients/{id}` |
| `lumina-orbit` | `start_session`, `run_cycle`, `run_full_session`, `approve_plan`, `pause_session`, `resume_session` | `orbit://sessions/{id}`, `orbit://sessions/{id}/insights`, `orbit://sessions/{id}/metrics` |

---

## Prompt Library

132 pre-built prompt templates across 5 industry verticals:

| Vertical | Templates | Categories |
|----------|-----------|------------|
| **SaaS / Technology** | 32 | Product recommendation, buying intent, brand knowledge, technical, competitive, industry authority |
| **Fintech** | 26 | Banking & payments, compliance, product, trust, competitive |
| **Healthtech** | 25 | Healthcare solutions, clinical, compliance, competitive |
| **E-commerce** | 25 | Platform selection, features, scalability, competitive |
| **Cloud / Infrastructure** | 25 | Cloud migration, services, enterprise, competitive |

Templates support `{brand}`, `{competitor_1}`, `{competitor_2}` placeholder substitution.

---

## Testing

```bash
# Run all tests
make test

# Run with coverage report
pytest tests/ -v --cov=src/lumina --cov-report=term-missing

# Run specific module
pytest tests/pulse/ -v

# Run excluding integration tests (no external services needed)
pytest tests/ -m "not integration"

# CI mode (80% coverage threshold)
make test-ci
```

**697 tests** across 10 modules — domain (pure, no mocks), application (mocked ports), infrastructure, and integration.

---

## Deployment

### Docker

```bash
# Build all images
make build

# Run production stack
docker compose up -d

# Run dev stack (with hot reload)
make dev
```

### GCP Cloud Run

```bash
# Deploy via Cloud Build
make deploy

# Or apply Terraform infrastructure
make deploy-terraform
```

Infrastructure is managed with Terraform:
- Cloud SQL (PostgreSQL 16, private IP, automated backups)
- Cloud Run (auto-scaling, 1-10 instances)
- Artifact Registry (Docker images)
- Secret Manager (API keys, credentials)
- HTTPS Load Balancer with managed SSL
- VPC with private networking
- Workload Identity Federation for GitHub Actions

### CI/CD

Automated via GitHub Actions:

1. **CI** (on push/PR to main): lint (ruff) + test (pytest, 80% coverage) + build Docker images
2. **Deploy** (on main after CI passes): push to Artifact Registry, run migrations, deploy to Cloud Run, smoke test, Slack notification

---

## Development

```bash
make dev          # Start dev environment
make test         # Run tests
make lint         # Lint with ruff
make lint-fix     # Auto-fix lint issues
make migrate      # Run database migrations
make shell-backend # Shell into backend container
make shell-db     # Open psql shell
make clean        # Clean up everything
make help         # Show all targets
```

---

## Pricing Tiers

| | Starter | Growth | Enterprise |
|---|---------|--------|------------|
| **Price** | ~$199/mo | ~$799/mo | $3,000-10,000/mo |
| **Modules** | PULSE + BEAM (basic) | All 4 modules | All + API + custom |
| **Brands** | 1 | Up to 5 | Unlimited |
| **AI Engines** | 2 (Claude, GPT-4o) | All 4 | All + custom endpoints |
| **Queries/mo** | 500 | 5,000 | Unlimited |
| **Support** | Self-serve | Email + chat | Dedicated CSM |

Agency tier available as add-on to Growth/Enterprise with white-label reporting.

---

## License

Proprietary. CONFIDENTIAL — Not for external distribution.

LUMINA is a SYNTHERA platform product. (c) 2026 Smeyatsky Labs. All rights reserved.
