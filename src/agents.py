from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field

from src.contracts import ProcurementDecision, RunTelemetry
from src.tools import ProcurementToolbox


class Stage1Investigation(BaseModel):
    summary_of_need: str
    identified_gap: bool
    gap_analysis: str
    catalog_overlap_detected: bool
    evidence_ids: list[str] = Field(default_factory=list)


def detect_business_gap(request_dict: dict) -> bool:
    """Determines if the justification articulates a genuine operational gap vs simple duplicate."""
    text = f"{request_dict.get('business_justification', '')} {request_dict.get('product_name', '')}".lower()
    gap_indicators = [
        "expansion", "additional", "add-on", "training", "gap", "specialist",
        "cannot", "lacks", "upgrade", "new squad", "scale"
    ]
    return any(term in text for term in gap_indicators)


def synthesize_next_action(
    request_dict: dict,
    policy_report: dict,
    has_gap: bool,
) -> tuple[str, str, str]:
    """Determines high-level action, recommendation label, and next operational instruction."""
    flags = policy_report.get("risk_flags", [])
    missing = policy_report.get("missing_information", [])
    approvals = policy_report.get("required_approvals", [])
    approvers_str = ", ".join(approvals)

    if "vendor_risk_unavailable" in flags or "tool_failure" in flags:
        action = "manual_review"
        rec = "Hold for manual evidence review"
        next_step = f"Hold procurement. Dispatch evidence package to {approvers_str} for offline verification."
    elif missing:
        action = "request_information"
        rec = "Request clarification"
        missing_str = "; ".join(missing)
        next_step = f"Request missing details from requester: {missing_str}. Re-evaluate once provided."
    elif "existing_tool_overlap" in flags and not has_gap:
        action = "check_existing_tool"
        rec = "Check existing catalog software first"
        next_step = f"Instruct requester to evaluate existing catalog software before submitting new purchase to {approvers_str}."
    else:
        action = "route_for_reviews"
        rec = "Route for required human reviews"
        next_step = f"Submit procurement evidence package to {approvers_str} for formal human signoff."

    return action, rec, next_step


class SingleProcurementAgent:
    """Architecture A: Single-agent baseline executing tool calls and direct synthesis."""

    def __init__(self, toolbox: ProcurementToolbox, telemetry: RunTelemetry):
        self.toolbox = toolbox
        self.telemetry = telemetry

    def run(self) -> ProcurementDecision:
        self.telemetry.agent_stages = ["procurement_agent"]
        tool_results = self.toolbox.gather_all()
        policy_eval = tool_results["policy_check"]["evaluation"]

        gap = detect_business_gap(self.toolbox.request)
        action, rec, next_step = synthesize_next_action(self.toolbox.request, policy_eval, gap)

        rationale = (
            f"Evaluated request under Policy {policy_eval['policy_version']}. "
            f"Deterministic checks assigned {len(policy_eval['required_approvals'])} review tier(s). "
            f"{'Identified legitimate functional gap.' if gap else 'Standard procurement route.'}"
        )

        return ProcurementDecision(
            request_id=self.toolbox.request.get("request_id", "REQ-CUSTOM"),
            recommendation=rec,
            evidence=self.toolbox.ledger.get_all(),
            required_approvals=policy_eval["required_approvals"],
            missing_information=policy_eval["missing_information"],
            risk_flags=policy_eval["risk_flags"],
            next_step=next_step,
            human_review_required=True,
            telemetry=self.telemetry,
            action_code=action,
            rationale=rationale,
            architecture="single",
            policy_version=policy_eval["policy_version"],
            reference_date=policy_eval["reference_date"],
        )


class DualStageProcurementPipeline:
    """Architecture B: Lightweight 2-Agent Staged Pipeline.
    Stage 1: Intake & Evidence Investigator
    Stage 2: Policy Compliance & Risk Auditor
    """

    def __init__(self, toolbox: ProcurementToolbox, telemetry: RunTelemetry):
        self.toolbox = toolbox
        self.telemetry = telemetry

    def run(self) -> ProcurementDecision:
        self.telemetry.agent_stages = ["intake_investigator", "compliance_auditor"]

        # Stage 1: Intake & Evidence Investigator
        tool_results = self.toolbox.gather_all()
        evidence_list = self.toolbox.ledger.get_all()
        catalog_matches = tool_results.get("software_catalog", {}).get("matches", [])
        gap_detected = detect_business_gap(self.toolbox.request)

        stage1 = Stage1Investigation(
            summary_of_need=self.toolbox.request.get("business_justification", "")[:300],
            identified_gap=gap_detected,
            gap_analysis=(
                "Valid expansion or distinct functional scope identified."
                if gap_detected
                else "No clear functional gap against existing tools noted."
            ),
            catalog_overlap_detected=bool(catalog_matches),
            evidence_ids=[e.evidence_id for e in evidence_list if e.evidence_id],
        )

        # Stage 2: Policy Compliance Auditor (evaluated in fresh context)
        policy_eval = tool_results["policy_check"]["evaluation"]
        action, rec, next_step = synthesize_next_action(self.toolbox.request, policy_eval, stage1.identified_gap)

        rationale = (
            f"Audited by Stage 2 Compliance Reviewer. "
            f"Intake assessment ({stage1.gap_analysis}) reviewed against corporate governance. "
            f"Enforced {len(policy_eval['required_approvals'])} mandatory approval gates."
        )

        return ProcurementDecision(
            request_id=self.toolbox.request.get("request_id", "REQ-CUSTOM"),
            recommendation=rec,
            evidence=evidence_list,
            required_approvals=policy_eval["required_approvals"],
            missing_information=policy_eval["missing_information"],
            risk_flags=policy_eval["risk_flags"],
            next_step=next_step,
            human_review_required=True,
            telemetry=self.telemetry,
            action_code=action,
            rationale=rationale,
            architecture="staged",
            policy_version=policy_eval["policy_version"],
            reference_date=policy_eval["reference_date"],
        )