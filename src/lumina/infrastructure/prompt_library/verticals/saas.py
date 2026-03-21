"""
SaaS / Technology Vertical — Prompt Templates

Pre-built prompt templates for monitoring AI visibility of SaaS and
technology brands across product recommendation, buying intent,
brand knowledge, technical, competitive, and industry authority categories.
"""

from lumina.pulse.domain.entities import PromptTemplate

SAAS_TEMPLATES: tuple[PromptTemplate, ...] = (
    # ------------------------------------------------------------------ #
    # Product Recommendation
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="saas-pr-001",
        text="What are the best {category} tools for enterprises?",
        category="product_recommendation",
        intent_tags=("discovery", "enterprise", "top_picks"),
    ),
    PromptTemplate(
        id="saas-pr-002",
        text="Compare {brand} vs {competitor_1} for {use_case}.",
        category="product_recommendation",
        intent_tags=("comparison", "head_to_head"),
    ),
    PromptTemplate(
        id="saas-pr-003",
        text="What {category} software do you recommend for a mid-size company?",
        category="product_recommendation",
        intent_tags=("discovery", "mid_market", "recommendation"),
    ),
    PromptTemplate(
        id="saas-pr-004",
        text="Which {category} platform offers the best value for money?",
        category="product_recommendation",
        intent_tags=("value", "pricing", "recommendation"),
    ),
    PromptTemplate(
        id="saas-pr-005",
        text="What are the top-rated {category} solutions in 2025?",
        category="product_recommendation",
        intent_tags=("discovery", "rankings", "recent"),
    ),
    PromptTemplate(
        id="saas-pr-006",
        text="Can you recommend a {category} tool that integrates well with existing workflows?",
        category="product_recommendation",
        intent_tags=("integration", "workflow", "recommendation"),
    ),

    # ------------------------------------------------------------------ #
    # Buying Intent
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="saas-bi-001",
        text="I'm evaluating {category} solutions. What should I consider?",
        category="buying_intent",
        intent_tags=("evaluation", "criteria", "purchase_decision"),
    ),
    PromptTemplate(
        id="saas-bi-002",
        text="Which {category} platform is best for {scenario}?",
        category="buying_intent",
        intent_tags=("use_case", "selection", "purchase_decision"),
    ),
    PromptTemplate(
        id="saas-bi-003",
        text="What factors should I weigh when choosing between {brand} and {competitor_1}?",
        category="buying_intent",
        intent_tags=("evaluation", "comparison", "decision_factors"),
    ),
    PromptTemplate(
        id="saas-bi-004",
        text="My team needs a {category} tool that scales to 10,000 users. What are my options?",
        category="buying_intent",
        intent_tags=("scalability", "enterprise", "purchase_decision"),
    ),
    PromptTemplate(
        id="saas-bi-005",
        text="What is the total cost of ownership for {brand} compared to {competitor_1}?",
        category="buying_intent",
        intent_tags=("pricing", "tco", "comparison"),
    ),

    # ------------------------------------------------------------------ #
    # Brand Knowledge
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="saas-bk-001",
        text="What is {brand}?",
        category="brand_knowledge",
        intent_tags=("identity", "overview"),
    ),
    PromptTemplate(
        id="saas-bk-002",
        text="Who founded {brand}?",
        category="brand_knowledge",
        intent_tags=("founders", "history"),
    ),
    PromptTemplate(
        id="saas-bk-003",
        text="What does {brand} do?",
        category="brand_knowledge",
        intent_tags=("identity", "products"),
    ),
    PromptTemplate(
        id="saas-bk-004",
        text="When was {brand} founded, and where is it headquartered?",
        category="brand_knowledge",
        intent_tags=("history", "geography"),
    ),
    PromptTemplate(
        id="saas-bk-005",
        text="What is {brand}'s mission and core values?",
        category="brand_knowledge",
        intent_tags=("mission", "values", "culture"),
    ),

    # ------------------------------------------------------------------ #
    # Technical
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="saas-tc-001",
        text="How does {brand} handle {technical_topic}?",
        category="technical",
        intent_tags=("architecture", "deep_dive"),
    ),
    PromptTemplate(
        id="saas-tc-002",
        text="What are {brand}'s key features?",
        category="technical",
        intent_tags=("features", "capabilities"),
    ),
    PromptTemplate(
        id="saas-tc-003",
        text="Does {brand} offer an API, and how comprehensive is it?",
        category="technical",
        intent_tags=("api", "developer_experience"),
    ),
    PromptTemplate(
        id="saas-tc-004",
        text="What security certifications does {brand} hold?",
        category="technical",
        intent_tags=("security", "compliance", "certifications"),
    ),
    PromptTemplate(
        id="saas-tc-005",
        text="How does {brand}'s architecture ensure high availability and uptime?",
        category="technical",
        intent_tags=("reliability", "architecture", "uptime"),
    ),
    PromptTemplate(
        id="saas-tc-006",
        text="What programming languages and frameworks does {brand} support?",
        category="technical",
        intent_tags=("developer_experience", "languages", "frameworks"),
    ),

    # ------------------------------------------------------------------ #
    # Competitive
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="saas-cp-001",
        text="How does {brand} compare to {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "head_to_head"),
    ),
    PromptTemplate(
        id="saas-cp-002",
        text="Is {brand} better than {competitor_2}?",
        category="competitive",
        intent_tags=("comparison", "preference"),
    ),
    PromptTemplate(
        id="saas-cp-003",
        text="What advantages does {brand} have over {competitor_1} and {competitor_2}?",
        category="competitive",
        intent_tags=("differentiation", "strengths"),
    ),
    PromptTemplate(
        id="saas-cp-004",
        text="Why do companies switch from {competitor_1} to {brand}?",
        category="competitive",
        intent_tags=("switching", "churn", "win_reasons"),
    ),
    PromptTemplate(
        id="saas-cp-005",
        text="What are the main differences between {brand} and {competitor_1} in terms of pricing and features?",
        category="competitive",
        intent_tags=("comparison", "pricing", "features"),
    ),

    # ------------------------------------------------------------------ #
    # Industry Authority
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="saas-ia-001",
        text="Who are the leaders in {category}?",
        category="industry_authority",
        intent_tags=("market_leaders", "landscape"),
    ),
    PromptTemplate(
        id="saas-ia-002",
        text="What companies are innovating in {category}?",
        category="industry_authority",
        intent_tags=("innovation", "emerging"),
    ),
    PromptTemplate(
        id="saas-ia-003",
        text="Which {category} vendors are considered best-in-class by analysts?",
        category="industry_authority",
        intent_tags=("analyst_recognition", "market_leaders"),
    ),
    PromptTemplate(
        id="saas-ia-004",
        text="What are the most important trends shaping the {category} market?",
        category="industry_authority",
        intent_tags=("trends", "market_dynamics"),
    ),
    PromptTemplate(
        id="saas-ia-005",
        text="Which {category} companies have the strongest customer satisfaction ratings?",
        category="industry_authority",
        intent_tags=("customer_satisfaction", "ratings"),
    ),
)
