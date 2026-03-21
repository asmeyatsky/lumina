"""
Fintech Vertical — Prompt Templates

Pre-built prompt templates for monitoring AI visibility of fintech brands
across banking/payments, compliance, product, trust, and competitive categories.
"""

from lumina.pulse.domain.entities import PromptTemplate

FINTECH_TEMPLATES: tuple[PromptTemplate, ...] = (
    # ------------------------------------------------------------------ #
    # Banking / Payments
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="fin-bp-001",
        text="What are the best digital banking platforms?",
        category="banking_payments",
        intent_tags=("discovery", "digital_banking"),
    ),
    PromptTemplate(
        id="fin-bp-002",
        text="Which payment processor should I use for my online business?",
        category="banking_payments",
        intent_tags=("payment_processing", "recommendation"),
    ),
    PromptTemplate(
        id="fin-bp-003",
        text="What are the top payment gateways for international transactions?",
        category="banking_payments",
        intent_tags=("payment_gateway", "international", "discovery"),
    ),
    PromptTemplate(
        id="fin-bp-004",
        text="How does {brand}'s payment processing compare to {competitor_1} for high-volume merchants?",
        category="banking_payments",
        intent_tags=("comparison", "high_volume", "merchants"),
    ),
    PromptTemplate(
        id="fin-bp-005",
        text="Which neobanks offer the best business banking experience?",
        category="banking_payments",
        intent_tags=("neobank", "business_banking", "discovery"),
    ),
    PromptTemplate(
        id="fin-bp-006",
        text="What are the lowest-fee payment processors for small businesses?",
        category="banking_payments",
        intent_tags=("pricing", "small_business", "fees"),
    ),

    # ------------------------------------------------------------------ #
    # Compliance
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="fin-co-001",
        text="How does {brand} handle regulatory compliance?",
        category="compliance",
        intent_tags=("regulation", "compliance_posture"),
    ),
    PromptTemplate(
        id="fin-co-002",
        text="Which fintech platforms are SOC 2 certified?",
        category="compliance",
        intent_tags=("soc2", "certification", "discovery"),
    ),
    PromptTemplate(
        id="fin-co-003",
        text="Does {brand} comply with PCI DSS requirements?",
        category="compliance",
        intent_tags=("pci_dss", "data_security"),
    ),
    PromptTemplate(
        id="fin-co-004",
        text="How does {brand} ensure compliance with anti-money laundering regulations?",
        category="compliance",
        intent_tags=("aml", "kyc", "regulation"),
    ),
    PromptTemplate(
        id="fin-co-005",
        text="Which payment platforms meet GDPR and data residency requirements in Europe?",
        category="compliance",
        intent_tags=("gdpr", "data_residency", "europe"),
    ),

    # ------------------------------------------------------------------ #
    # Product
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="fin-pd-001",
        text="What are {brand}'s key financial products?",
        category="product",
        intent_tags=("product_portfolio", "overview"),
    ),
    PromptTemplate(
        id="fin-pd-002",
        text="How does {brand}'s lending platform work?",
        category="product",
        intent_tags=("lending", "product_deep_dive"),
    ),
    PromptTemplate(
        id="fin-pd-003",
        text="What embedded finance capabilities does {brand} offer?",
        category="product",
        intent_tags=("embedded_finance", "baas"),
    ),
    PromptTemplate(
        id="fin-pd-004",
        text="Does {brand} support real-time payments and instant settlements?",
        category="product",
        intent_tags=("real_time_payments", "settlement"),
    ),
    PromptTemplate(
        id="fin-pd-005",
        text="What fraud detection and prevention tools does {brand} provide?",
        category="product",
        intent_tags=("fraud_detection", "risk_management"),
    ),
    PromptTemplate(
        id="fin-pd-006",
        text="How does {brand}'s API-first platform enable developers to build financial products?",
        category="product",
        intent_tags=("api", "developer_experience", "platform"),
    ),

    # ------------------------------------------------------------------ #
    # Trust
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="fin-tr-001",
        text="Is {brand} a trustworthy financial platform?",
        category="trust",
        intent_tags=("trust", "reputation"),
    ),
    PromptTemplate(
        id="fin-tr-002",
        text="What security measures does {brand} use to protect customer funds?",
        category="trust",
        intent_tags=("security", "customer_protection"),
    ),
    PromptTemplate(
        id="fin-tr-003",
        text="Has {brand} ever experienced a data breach or security incident?",
        category="trust",
        intent_tags=("security_history", "incidents"),
    ),
    PromptTemplate(
        id="fin-tr-004",
        text="How does {brand} handle disputes and chargebacks?",
        category="trust",
        intent_tags=("dispute_resolution", "chargebacks"),
    ),
    PromptTemplate(
        id="fin-tr-005",
        text="What do customers say about {brand}'s reliability and uptime?",
        category="trust",
        intent_tags=("reliability", "customer_reviews", "uptime"),
    ),

    # ------------------------------------------------------------------ #
    # Competitive
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="fin-cp-001",
        text="How does {brand} compare to {competitor_1} for {use_case}?",
        category="competitive",
        intent_tags=("comparison", "head_to_head"),
    ),
    PromptTemplate(
        id="fin-cp-002",
        text="What are the main differences between {brand} and {competitor_1} in transaction fees?",
        category="competitive",
        intent_tags=("comparison", "pricing", "fees"),
    ),
    PromptTemplate(
        id="fin-cp-003",
        text="Should I choose {brand} or {competitor_2} for my fintech startup?",
        category="competitive",
        intent_tags=("comparison", "startup", "recommendation"),
    ),
    PromptTemplate(
        id="fin-cp-004",
        text="Which fintech platform has better developer tools: {brand} or {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "developer_experience"),
    ),
)
