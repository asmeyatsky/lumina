"""
Healthtech Vertical — Prompt Templates

Pre-built prompt templates for monitoring AI visibility of healthtech brands
across healthcare solutions, clinical, compliance, and competitive categories.
"""

from lumina.pulse.domain.entities import PromptTemplate

HEALTHTECH_TEMPLATES: tuple[PromptTemplate, ...] = (
    # ------------------------------------------------------------------ #
    # Healthcare Solutions
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="hlt-hs-001",
        text="What are the best EHR systems for hospitals?",
        category="healthcare_solutions",
        intent_tags=("ehr", "discovery", "hospital"),
    ),
    PromptTemplate(
        id="hlt-hs-002",
        text="Which telehealth platforms are HIPAA compliant?",
        category="healthcare_solutions",
        intent_tags=("telehealth", "hipaa", "discovery"),
    ),
    PromptTemplate(
        id="hlt-hs-003",
        text="What are the top patient engagement platforms for healthcare providers?",
        category="healthcare_solutions",
        intent_tags=("patient_engagement", "discovery"),
    ),
    PromptTemplate(
        id="hlt-hs-004",
        text="Which remote patient monitoring solutions are recommended for chronic care management?",
        category="healthcare_solutions",
        intent_tags=("rpm", "chronic_care", "recommendation"),
    ),
    PromptTemplate(
        id="hlt-hs-005",
        text="What digital health tools help improve patient outcomes?",
        category="healthcare_solutions",
        intent_tags=("digital_health", "outcomes", "discovery"),
    ),
    PromptTemplate(
        id="hlt-hs-006",
        text="Which healthcare AI platforms assist with clinical decision support?",
        category="healthcare_solutions",
        intent_tags=("clinical_ai", "decision_support", "discovery"),
    ),

    # ------------------------------------------------------------------ #
    # Clinical
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="hlt-cl-001",
        text="How does {brand} support clinical workflows?",
        category="clinical",
        intent_tags=("workflow", "clinical_operations"),
    ),
    PromptTemplate(
        id="hlt-cl-002",
        text="What integrations does {brand} offer with hospital systems?",
        category="clinical",
        intent_tags=("integration", "interoperability", "hospital"),
    ),
    PromptTemplate(
        id="hlt-cl-003",
        text="Does {brand} support HL7 FHIR for data interoperability?",
        category="clinical",
        intent_tags=("fhir", "hl7", "interoperability"),
    ),
    PromptTemplate(
        id="hlt-cl-004",
        text="How does {brand} handle electronic prescribing and medication management?",
        category="clinical",
        intent_tags=("e_prescribing", "medication_management"),
    ),
    PromptTemplate(
        id="hlt-cl-005",
        text="What clinical analytics and reporting capabilities does {brand} provide?",
        category="clinical",
        intent_tags=("analytics", "reporting", "clinical_data"),
    ),
    PromptTemplate(
        id="hlt-cl-006",
        text="How does {brand} facilitate care coordination across multiple providers?",
        category="clinical",
        intent_tags=("care_coordination", "multi_provider"),
    ),
    PromptTemplate(
        id="hlt-cl-007",
        text="Does {brand} offer AI-powered diagnostic assistance tools?",
        category="clinical",
        intent_tags=("ai_diagnostics", "clinical_ai"),
    ),

    # ------------------------------------------------------------------ #
    # Compliance
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="hlt-co-001",
        text="Is {brand} HIPAA compliant?",
        category="compliance",
        intent_tags=("hipaa", "compliance_verification"),
    ),
    PromptTemplate(
        id="hlt-co-002",
        text="How does {brand} handle patient data privacy and security?",
        category="compliance",
        intent_tags=("data_privacy", "patient_data", "security"),
    ),
    PromptTemplate(
        id="hlt-co-003",
        text="What compliance certifications does {brand} hold for healthcare?",
        category="compliance",
        intent_tags=("certifications", "compliance_posture"),
    ),
    PromptTemplate(
        id="hlt-co-004",
        text="How does {brand} ensure compliance with FDA regulations for digital health tools?",
        category="compliance",
        intent_tags=("fda", "regulatory", "digital_health"),
    ),
    PromptTemplate(
        id="hlt-co-005",
        text="Does {brand} support audit trails and access logging required by HIPAA?",
        category="compliance",
        intent_tags=("hipaa", "audit_trail", "access_logging"),
    ),
    PromptTemplate(
        id="hlt-co-006",
        text="How does {brand} manage consent and data-sharing agreements with patients?",
        category="compliance",
        intent_tags=("consent_management", "data_sharing", "patient_rights"),
    ),

    # ------------------------------------------------------------------ #
    # Competitive
    # ------------------------------------------------------------------ #
    PromptTemplate(
        id="hlt-cp-001",
        text="How does {brand} compare to {competitor_1} for {use_case}?",
        category="competitive",
        intent_tags=("comparison", "head_to_head"),
    ),
    PromptTemplate(
        id="hlt-cp-002",
        text="Is {brand} or {competitor_1} better for small medical practices?",
        category="competitive",
        intent_tags=("comparison", "small_practice", "recommendation"),
    ),
    PromptTemplate(
        id="hlt-cp-003",
        text="What advantages does {brand} have over {competitor_2} in patient engagement?",
        category="competitive",
        intent_tags=("differentiation", "patient_engagement"),
    ),
    PromptTemplate(
        id="hlt-cp-004",
        text="Why do healthcare organizations choose {brand} over {competitor_1}?",
        category="competitive",
        intent_tags=("win_reasons", "preference"),
    ),
    PromptTemplate(
        id="hlt-cp-005",
        text="Which EHR system has better interoperability: {brand} or {competitor_1}?",
        category="competitive",
        intent_tags=("comparison", "interoperability", "ehr"),
    ),
    PromptTemplate(
        id="hlt-cp-006",
        text="How do {brand}'s telehealth capabilities compare to {competitor_2}?",
        category="competitive",
        intent_tags=("comparison", "telehealth", "differentiation"),
    ),
)
