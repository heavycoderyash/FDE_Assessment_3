from __future__ import annotations

import time
from typing import Any
from src.contracts import Architecture, ProcurementDecision, PurchaseRequestInput, RunTelemetry
from src.data_access import get_request
from src.tools import ProcurementToolbox
from src.agents import SingleProcurementAgent, DualStageProcurementPipeline


def analyze_request(
    request_data: dict | PurchaseRequestInput,
    architecture: Architecture = "single",
    mode: str = "offline",
    *,
    data_dir: Any = None,
    risk_fetcher: Any = None,
) -> ProcurementDecision:
    """Core analysis orchestrator supporting single and staged architectures."""
    start_time = time.perf_counter()

    if isinstance(request_data, dict):
        validated_req = PurchaseRequestInput.model_validate(request_data)
    else:
        validated_req = request_data

    telemetry = RunTelemetry(
        llm_calls=0 if mode == "offline" else 1,
        tool_calls=0,
        mode=mode,
        architecture=architecture,
    )

    kwargs = {}
    if data_dir is not None:
        kwargs["data_dir"] = data_dir
    if risk_fetcher is not None:
        kwargs["risk_fetcher"] = risk_fetcher

    toolbox = ProcurementToolbox(validated_req.model_dump(), telemetry, **kwargs)

    if architecture == "single":
        decision = SingleProcurementAgent(toolbox, telemetry).run()
    elif architecture == "staged":
        decision = DualStageProcurementPipeline(toolbox, telemetry).run()
    else:
        raise ValueError(f"Unsupported architecture: {architecture}")

    telemetry.latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    decision.telemetry = telemetry
    return decision


def handle_request(request_id: str, architecture: Architecture = "single") -> ProcurementDecision:
    """Official assessment adapter callable by public & hidden evaluation harnesses."""
    raw_request = get_request(request_id)
    return analyze_request(raw_request, architecture=architecture, mode="offline")