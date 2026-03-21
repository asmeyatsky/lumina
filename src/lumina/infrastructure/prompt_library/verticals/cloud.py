"""
Cloud / Infrastructure Vertical — Prompt Templates

Pre-built prompt templates for monitoring AI visibility of cloud and
infrastructure brands across cloud migration, services, enterprise,
and competitive categories.
"""

from lumina.pulse.domain.entities import PromptTemplate

CLOUD_TEMPLATES: tuple[PromptTemplate, ...] = (
    # ------------------------------------------------------------------ #
    # Cloud Migration
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="cld-cm-001",
        text="What's the best cloud provider for {use_case}?",
        category="cloud_migration",
        intent_tags=("discovery", "cloud_selection", "use_case"),
    ),
    PromptTemplate(
        id="cld-cm-002",
        text="How do I migrate from {competitor_1} to {brand}?",
        category="cloud_migration",
        intent_tags=("migration", "planning", "cloud_transition"),
    ),
    PromptTemplate(
        id="cld-cm-003",
        text="What are the best practices for migrating legacy applications to {brand}?",
        category="cloud_migration",
        intent_tags=("migration", "legacy", "best_practices"),
    ),
    PromptTemplate(
        id="cld-cm-004",
        text="How long does a typical cloud migration to {brand} take for a mid-size company?",
        category="cloud_migration",
        intent_tags=("migration", "timeline", "planning"),
    ),
    PromptTemplate(
        id="cld-cm-005",
        text="What tools does {brand} provide to assess cloud readiness and plan migrations?",
        category="cloud_migration",
        intent_tags=("migration_tools", "assessment", "planning"),
    ),
    PromptTemplate(
        id="cld-cm-006",
        text="What are the hidden costs of migrating to {brand} that teams often overlook?",
        category="cloud_migration",
        intent_tags=("migration", "pricing", "hidden_costs"),
    ),

    # ------------------------------------------------------------------ #
    # Services
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="cld-sv-001",
        text="What managed services does {brand} offer?",
        category="services",
        intent_tags=("managed_services", "portfolio"),
    ),
    PromptTemplate(
        id="cld-sv-002",
        text="How does {brand}'s Kubernetes offering compare to other managed Kubernetes services?",
        category="services",
        intent_tags=("kubernetes", "container_orchestration", "comparison"),
    ),
    PromptTemplate(
        id="cld-sv-003",
        text="What serverless computing options does {brand} provide?",
        category="services",
        intent_tags=("serverless", "functions", "compute"),
    ),
    PromptTemplate(
        id="cld-sv-004",
        text="What database services does {brand} offer, and how do they compare?",
        category="services",
        intent_tags=("database", "managed_database", "comparison"),
    ),
    PromptTemplate(
        id="cld-sv-005",
        text="Does {brand} offer managed AI and machine learning services?",
        category="services",
        intent_tags=("ai_ml", "managed_services"),
    ),
    PromptTemplate(
        id="cld-sv-006",
        text="What networking and CDN capabilities does {brand} provide?",
        category="services",
        intent_tags=("networking", "cdn", "edge"),
    ),
    PromptTemplate(
        id="cld-sv-007",
        text="How does {brand} support DevOps pipelines and CI/CD workflows?",
        category="services",
        intent_tags=("devops", "ci_cd", "automation"),
    ),

    # ------------------------------------------------------------------ #
    # Enterprise
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="cld-en-001",
        text="Which cloud provider is best for enterprise workloads?",
        category="enterprise",
        intent_tags=("enterprise", "discovery", "recommendation"),
    ),
    PromptTemplate(
        id="cld-en-002",
        text="What compliance certifications does {brand} have?",
        category="enterprise",
        intent_tags=("compliance", "certifications", "enterprise"),
    ),
    PromptTemplate(
        id="cld-en-003",
        text="How does {brand} support hybrid and multi-cloud architectures?",
        category="enterprise",
        intent_tags=("hybrid_cloud", "multi_cloud", "architecture"),
    ),
    PromptTemplate(
        id="cld-en-004",
        text="What enterprise support tiers and SLAs does {brand} offer?",
        category="enterprise",
        intent_tags=("support", "sla", "enterprise"),
    ),
    PromptTemplate(
        id="cld-en-005",
        text="How does {brand} handle data sovereignty and regional compliance requirements?",
        category="enterprise",
        intent_tags=("data_sovereignty", "regional_compliance", "governance"),
    ),
    PromptTemplate(
        id="cld-en-006",
        text="What cost management and optimization tools does {brand} provide for enterprise accounts?",
        category="enterprise",
        intent_tags=("cost_management", "optimization", "finops"),
    ),

    # ------------------------------------------------------------------ #
    # Competitive
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="cld-cp-001",
        text="How does {brand} compare to {competitor_1} for cloud infrastructure?",
        category="competitive",
        intent_tags=("comparison", "head_to_head", "infrastructure"),
    ),
    PromptTemplate(
        id="cld-cp-002",
        text="Is {brand} or {competitor_2} better for startups?",
        category="competitive",
        intent_tags=("comparison", "startup", "recommendation"),
    ),
    PromptTemplate(
        id="cld-cp-003",
        text="What are the pricing differences between {brand} and {competitor_1} for compute instances?",
        category="competitive",
        intent_tags=("comparison", "pricing", "compute"),
    ),
    PromptTemplate(
        id="cld-cp-004",
        text="Which cloud provider has the best global network: {brand} or {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "global_network", "latency"),
    ),
    PromptTemplate(
        id="cld-cp-005",
        text="Why are companies choosing {brand} over {competitor_1} for AI workloads?",
        category="competitive",
        intent_tags=("comparison", "ai_workloads", "win_reasons"),
    ),
    PromptTemplate(
        id="cld-cp-006",
        text="Which cloud provider offers better observability and monitoring tools: {brand} or {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "observability", "monitoring"),
    ),
)
