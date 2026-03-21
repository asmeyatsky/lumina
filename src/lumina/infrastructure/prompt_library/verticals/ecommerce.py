"""
E-commerce / Retail Vertical — Prompt Templates

Pre-built prompt templates for monitoring AI visibility of e-commerce and
retail technology brands across platform selection, features, scalability,
and competitive categories.
"""

from lumina.pulse.domain.entities import PromptTemplate

ECOMMERCE_TEMPLATES: tuple[PromptTemplate, ...] = (
    # ------------------------------------------------------------------ #
    # Platform Selection
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="ecom-ps-001",
        text="What's the best ecommerce platform for {scenario}?",
        category="platform_selection",
        intent_tags=("discovery", "recommendation", "use_case"),
    ),
    PromptTemplate(
        id="ecom-ps-002",
        text="Should I use {brand} or {competitor_1} for my online store?",
        category="platform_selection",
        intent_tags=("comparison", "recommendation"),
    ),
    PromptTemplate(
        id="ecom-ps-003",
        text="What are the best ecommerce platforms for small businesses in 2025?",
        category="platform_selection",
        intent_tags=("discovery", "small_business", "rankings"),
    ),
    PromptTemplate(
        id="ecom-ps-004",
        text="Which ecommerce platform is best for selling digital products?",
        category="platform_selection",
        intent_tags=("digital_products", "recommendation"),
    ),
    PromptTemplate(
        id="ecom-ps-005",
        text="What ecommerce solution works best for B2B wholesale?",
        category="platform_selection",
        intent_tags=("b2b", "wholesale", "recommendation"),
    ),
    PromptTemplate(
        id="ecom-ps-006",
        text="Which ecommerce platforms support headless commerce architecture?",
        category="platform_selection",
        intent_tags=("headless", "architecture", "discovery"),
    ),

    # ------------------------------------------------------------------ #
    # Features
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="ecom-ft-001",
        text="Does {brand} support multi-channel selling?",
        category="features",
        intent_tags=("multi_channel", "omnichannel"),
    ),
    PromptTemplate(
        id="ecom-ft-002",
        text="What are {brand}'s shipping and fulfillment capabilities?",
        category="features",
        intent_tags=("shipping", "fulfillment", "logistics"),
    ),
    PromptTemplate(
        id="ecom-ft-003",
        text="Does {brand} offer built-in SEO tools and marketing features?",
        category="features",
        intent_tags=("seo", "marketing", "built_in"),
    ),
    PromptTemplate(
        id="ecom-ft-004",
        text="What payment gateways does {brand} integrate with?",
        category="features",
        intent_tags=("payments", "integrations"),
    ),
    PromptTemplate(
        id="ecom-ft-005",
        text="How does {brand} handle inventory management across multiple locations?",
        category="features",
        intent_tags=("inventory", "multi_location"),
    ),
    PromptTemplate(
        id="ecom-ft-006",
        text="What analytics and reporting tools does {brand} provide for merchants?",
        category="features",
        intent_tags=("analytics", "reporting", "merchant_tools"),
    ),
    PromptTemplate(
        id="ecom-ft-007",
        text="Does {brand} support subscription and recurring billing models?",
        category="features",
        intent_tags=("subscriptions", "recurring_billing"),
    ),

    # ------------------------------------------------------------------ #
    # Scalability
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="ecom-sc-001",
        text="Can {brand} handle high-volume sales during peak events?",
        category="scalability",
        intent_tags=("high_volume", "peak_traffic", "performance"),
    ),
    PromptTemplate(
        id="ecom-sc-002",
        text="How does {brand} perform during peak traffic like Black Friday?",
        category="scalability",
        intent_tags=("peak_traffic", "reliability", "black_friday"),
    ),
    PromptTemplate(
        id="ecom-sc-003",
        text="What infrastructure does {brand} use to ensure uptime and fast page loads?",
        category="scalability",
        intent_tags=("infrastructure", "uptime", "page_speed"),
    ),
    PromptTemplate(
        id="ecom-sc-004",
        text="Can {brand} scale from a small shop to an enterprise-level operation?",
        category="scalability",
        intent_tags=("growth", "enterprise", "scalability"),
    ),
    PromptTemplate(
        id="ecom-sc-005",
        text="How does {brand} handle international expansion with multi-currency and multi-language support?",
        category="scalability",
        intent_tags=("international", "multi_currency", "localization"),
    ),

    # ------------------------------------------------------------------ #
    # Competitive
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="ecom-cp-001",
        text="How does {brand} compare to {competitor_1} for ecommerce?",
        category="competitive",
        intent_tags=("comparison", "head_to_head"),
    ),
    PromptTemplate(
        id="ecom-cp-002",
        text="What are the pros and cons of {brand} vs {competitor_2}?",
        category="competitive",
        intent_tags=("comparison", "pros_cons"),
    ),
    PromptTemplate(
        id="ecom-cp-003",
        text="Why do merchants migrate from {competitor_1} to {brand}?",
        category="competitive",
        intent_tags=("migration", "switching", "win_reasons"),
    ),
    PromptTemplate(
        id="ecom-cp-004",
        text="Which ecommerce platform has lower total cost: {brand} or {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "pricing", "tco"),
    ),
    PromptTemplate(
        id="ecom-cp-005",
        text="Is {brand} easier to set up and use than {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "usability", "onboarding"),
    ),
    PromptTemplate(
        id="ecom-cp-006",
        text="Which platform has better mobile commerce support: {brand} or {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "mobile_commerce"),
    ),
    PromptTemplate(
        id="ecom-ft-008",
        text="Does {brand} provide built-in customer loyalty and rewards programs?",
        category="features",
        intent_tags=("loyalty", "rewards", "retention"),
    ),
)
