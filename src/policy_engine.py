from __future__ import annotations

from datetime import date
from decimal import Decimal
import re

POLICY_VERSION = "2026.09"
REFERENCE_DATE = date(2026, 9, 30)

# Canonical approval hierarchy
APPROVAL_ROLES = {
    "Manager",
    "Department Head",
    "Procurement",
    "Finance",
    "CFO",
    "Security",
    "Privacy",
    "Legal",
}

# High-risk data classifications requiring mandatory Security review
SECURITY_SENSITIVE_DATA = {
    "source_code",
    "production_telemetry",
    "production",
    "cloud_account",
    "confidential_documents",
    "employee_pii",
    "customer_pii",
    "credentials",
    "secrets",
    "credentials_secrets",
}

PII_DATA = {"employee_pii", "customer_pii"}
PERMITTED_DATA_LEVELS = SECURITY_SENSITIVE_DATA | {
    "none",
    "public",
    "internal_documents",
    "internal_marketing",
    "internal",
}

# Prompt injection heuristic signature
INJECTION_PATTERN = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:procurement\s+)?rules|ignore\s+policy|bypass\s+(?:approval|control|review)|"
    r"cfo[ -]approved|approve\s+immediately|reveal\s+(?:secret|api|key)|system\s+instruction)",
    re.IGNORECASE,
)


def get_financial_approvals(annual_cost: float | None) -> list[str]:
    """Calculates deterministic minimum approvals based on policy spend tiers."""
    if annual_cost is None:
        return ["Department Head", "Finance", "Procurement"]

    cost = Decimal(str(annual_cost))
    if cost <= Decimal("1000.00"):
        return ["Manager"]
    elif cost <= Decimal("10000.00"):
        return ["Department Head", "Procurement"]
    elif cost <= Decimal("25000.00"):
        return ["Department Head", "Finance", "Procurement"]
    else:
        return ["Department Head", "Finance", "CFO", "Procurement"]


def is_vendor_review_current(review_date_str: str | None) -> bool:
    """Verifies if a vendor security assessment is within 365 days of reference snapshot."""
    if not review_date_str:
        return False
    try:
        rev_date = date.fromisoformat(str(review_date_str).strip())
        delta = (REFERENCE_DATE - rev_date).days
        return 0 <= delta <= 365
    except (ValueError, TypeError):
        return False


def normalize_token(s: str | None) -> str:
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_")


class PolicyEngine:
    """Deterministic implementation of Procurement Policy 2026.09."""

    @classmethod
    def evaluate(cls, request_data: dict, tool_results: dict) -> dict:
        req = request_data
        cost = req.get("annual_cost_usd")
        data_level = normalize_token(req.get("data_access_level"))

        required_approvals = get_financial_approvals(cost)
        missing_info: list[str] = []
        risk_flags: list[str] = []
        audit_reasons: list[str] = []

        def trigger_review(role: str, flag: str, reason: str):
            if role not in required_approvals:
                required_approvals.append(role)
            if flag not in risk_flags:
                risk_flags.append(flag)
            audit_reasons.append(reason)

        # 1. Required Request Information Checks
        emp_info = tool_results.get("requester_budget", {}).get("employee")
        if not emp_info:
            missing_info.append("Valid requester and department verification")

        if req.get("annual_cost_usd") is None:
            missing_info.append("Annual cost estimate")
        if req.get("user_count") is None:
            missing_info.append("Number of users/licenses")
        if not req.get("product_name"):
            missing_info.append("Product name")
        if not req.get("vendor_name"):
            missing_info.append("Vendor name")
        if not req.get("business_justification"):
            missing_info.append("Business justification")
        if data_level not in PERMITTED_DATA_LEVELS:
            missing_info.append("Intended data-access level")

        # 2. Budget Verification Check
        budget_info = tool_results.get("requester_budget", {}).get("budget")
        if budget_info and cost is not None:
            available = Decimal(str(budget_info.get("available_usd", 0)))
            if Decimal(str(cost)) > available:
                trigger_review(
                    "Finance",
                    "budget_insufficient",
                    f"Policy Sec 2: Cost ${cost:,.2f} exceeds department available budget ${available:,.2f}.",
                )
        elif not budget_info:
            missing_info.append("Department budget verification")
            trigger_review("Finance", "budget_unavailable", "Policy Sec 2: Department budget record not found.")

        # 3. Existing Catalog Overlap Check
        catalog_matches = tool_results.get("software_catalog", {}).get("matches", [])
        if catalog_matches:
            risk_flags.append("existing_tool_overlap")
            audit_reasons.append(f"Policy Sec 3: Identified {len(catalog_matches)} potential catalog alternative(s).")

        # 4. Security Review Triggers
        integrations_str = " ".join(req.get("requested_integrations") or []).lower()
        if data_level in SECURITY_SENSITIVE_DATA or any(
            kw in integrations_str for kw in ["cloud", "production", "source", "git", "credential", "secret"]
        ):
            trigger_review(
                "Security",
                "security_review_required",
                "Policy Sec 5: Source code, production integrations, or sensitive documents require Security audit.",
            )

        # 5. Vendor Assessment & Risk Service Verification
        vendor_rec = tool_results.get("vendor_registry", {}).get("vendor") or {}
        risk_res = tool_results.get("vendor_risk", {})
        risk_api_data = risk_res.get("assessment") or {}

        if risk_res.get("status") != "ok":
            risk_flags.append("vendor_risk_unavailable")
            missing_info.append("Live external vendor security assessment")
            trigger_review(
                "Security",
                "security_review_required",
                "Policy Sec 10: External vendor risk service unavailable; favorable status cannot be assumed.",
            )

        reg_sec_status = normalize_token(vendor_rec.get("security_status"))
        api_sec_status = normalize_token(risk_api_data.get("security_review_status"))
        reg_date = vendor_rec.get("security_review_date")
        api_date = risk_api_data.get("last_review_date")

        # Expiration Check
        reg_is_current = is_vendor_review_current(reg_date)
        api_is_current = is_vendor_review_current(api_date)

        if not reg_is_current or not api_is_current or reg_sec_status != "approved" or api_sec_status != "approved":
            trigger_review(
                "Security",
                "security_review_required",
                "Policy Sec 5: Incomplete or unverified vendor security assessment.",
            )
            if (reg_date and not reg_is_current) or (api_date and not api_is_current) or api_sec_status == "expired":
                if "vendor_review_expired" not in risk_flags:
                    risk_flags.append("vendor_review_expired")

        # Discrepancy Check between internal registry and external service
        status_map = {"pending": "not_completed", "approved": "approved", "expired": "expired", "unknown": "unknown"}
        norm_reg = status_map.get(reg_sec_status, reg_sec_status)
        if vendor_rec and risk_api_data:
            if (norm_reg != api_sec_status) or (reg_date or None) != (api_date or None):
                if "conflicting_vendor_evidence" not in risk_flags:
                    risk_flags.append("conflicting_vendor_evidence")
                trigger_review(
                    "Security",
                    "security_review_required",
                    "Policy Sec 5: Discrepancy between internal registry and external risk API.",
                )

        # 6. Privacy Review
        stores_outside = risk_api_data.get("stores_data_outside_region") is True
        if data_level in PII_DATA or (stores_outside and data_level in SECURITY_SENSITIVE_DATA):
            trigger_review(
                "Privacy",
                "privacy_review_required",
                "Policy Sec 6: PII or cross-region processing of sensitive data requires Privacy review.",
            )

        # 7. Legal Review
        is_new_vendor = normalize_token(vendor_rec.get("procurement_status")) != "approved"
        legal_terms = normalize_token(vendor_rec.get("legal_terms_status"))
        if (is_new_vendor and cost is not None and cost >= 10000) or legal_terms not in {"approved", "standard"} or stores_outside:
            trigger_review(
                "Legal",
                "legal_review_required",
                "Policy Sec 7: New vendor with >=$10k spend, unapproved legal terms, or cross-region transfer.",
            )

        # 8. Untrusted Business Text / Prompt Injection Detection
        corpus = f"{req.get('business_justification', '')} {req.get('product_name', '')}"
        if INJECTION_PATTERN.search(corpus):
            risk_flags.append("prompt_injection_detected")
            audit_reasons.append("Policy Sec 9: Detected override or injection attempt in request data.")

        if missing_info:
            risk_flags.append("missing_information")

        return {
            "required_approvals": list(dict.fromkeys(required_approvals)),
            "missing_information": list(dict.fromkeys(missing_info)),
            "risk_flags": list(dict.fromkeys(risk_flags)),
            "audit_reasons": audit_reasons,
            "human_review_required": True,
            "reference_date": REFERENCE_DATE.isoformat(),
            "policy_version": POLICY_VERSION,
        }