from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from src.contracts import ProcurementDecision
from src.solution import analyze_request

ROOT = Path(__file__).resolve().parents[1]


def run_comparative_evals():
    cases_path = ROOT / "evals" / "public_cases.json"
    requests_path = ROOT / "data" / "requests.json"
    requests = {r["request_id"]: r for r in json.loads(requests_path.read_text(encoding="utf-8"))}
    public_cases = json.loads(cases_path.read_text(encoding="utf-8"))

    print("\n" + "=" * 70)
    print("AI PROCUREMENT COPILOT: COMPARATIVE ARCHITECTURE EVALUATION")
    print("=" * 70 + "\n")

    summary_rows = []

    for arch in ["single", "staged"]:
        print(f"--> Evaluating Architecture: {arch.upper()}")
        arch_start = time.perf_counter()
        passed_count = 0

        for case in public_cases:
            req_id = case["request_id"]
            req_data = requests[req_id]

            t0 = time.perf_counter()
            decision: ProcurementDecision = analyze_request(req_data, architecture=arch, mode="offline")
            lat = (time.perf_counter() - t0) * 1000

            # Evaluate basic expectations
            has_human = decision.human_review_required is True
            has_evidence = len(decision.evidence) >= case["expectations"].get("min_evidence_items", 1)
            passed = has_human and has_evidence
            if passed:
                passed_count += 1

            summary_rows.append({
                "case_id": case["case_id"],
                "request_id": req_id,
                "architecture": arch,
                "recommendation": decision.recommendation,
                "latency_ms": round(lat, 2),
                "tool_calls": decision.telemetry.tool_calls if decision.telemetry else 0,
                "approvals_count": len(decision.required_approvals),
                "risk_flags_count": len(decision.risk_flags),
                "passed": passed,
            })
            print(f"    [{'PASS' if passed else 'FAIL'}] {case['case_id']} ({req_id}): {decision.recommendation} [{lat:.1f} ms]")

        total_time = (time.perf_counter() - arch_start) * 1000
        print(f"Summary {arch.upper()}: {passed_count}/{len(public_cases)} passed in {total_time:.1f} ms\n")

    out_file = ROOT / "evals" / "architecture_comparison_summary.csv"
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Results successfully saved to: {out_file.relative_to(ROOT)}")


if __name__ == "__main__":
    run_comparative_evals()