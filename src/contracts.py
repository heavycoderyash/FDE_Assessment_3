from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class EvidenceItem(BaseModel):
    evidence_id: str | None = Field(default=None, description="Unique trace identifier e.g. EV-001")
    source: str = Field(description="Tool/data source name")
    finding: str = Field(description="Concise factual finding")
    reference: str | None = Field(default=None, description="Optional record ID / policy section / endpoint")


class RunTelemetry(BaseModel):
    llm_calls: int = 0
    tool_calls: int = 0
    tool_names: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0
    mode: str = "offline"
    architecture: str = "single"
    agent_stages: list[str] = Field(default_factory=list)
    execution_trace: list[dict] = Field(default_factory=list)


class ProcurementDecision(BaseModel):
    request_id: str
    recommendation: str = Field(description="High-level advisory recommendation")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    next_step: str = Field(description="Explicit next operational step for human reviewers")
    human_review_required: bool = True
    telemetry: RunTelemetry | None = None
    action_code: str = "manual_review"
    rationale: str = ""
    architecture: str = "single"
    policy_version: str = "2026.09"
    reference_date: str = "2026-09-30"


class PurchaseRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    request_id: str = Field(default="REQ-CUSTOM", min_length=1, max_length=100)
    requester_id: str = Field(default="", max_length=50)
    product_name: str = Field(default="", max_length=200)
    vendor_name: str = Field(default="", max_length=200)
    category: str = Field(default="", max_length=150)
    annual_cost_usd: float | None = Field(default=None, ge=0)
    user_count: int | None = Field(default=None, gt=0)
    business_justification: str = Field(default="", max_length=5000)
    data_access_level: str = Field(default="unknown", max_length=100)
    requested_integrations: list[str] | None = Field(default_factory=list)
    urgency: str = Field(default="normal", max_length=50)

    @field_validator("annual_cost_usd")
    @classmethod
    def validate_cents(cls, v: float | None) -> float | None:
        if v is not None:
            from decimal import Decimal
            d = Decimal(str(v))
            if d.as_tuple().exponent < -2:
                raise ValueError("Annual cost cannot have more than 2 decimal places")
        return v


Architecture = Literal["single", "staged"]