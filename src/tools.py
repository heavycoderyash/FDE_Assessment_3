from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Callable

from src.contracts import EvidenceItem, RunTelemetry
from src.policy_engine import PolicyEngine
from src.vendor_client import get_vendor_risk

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def read_csv_records(filename: str, directory: Path = DATA_DIR) -> list[dict[str, str]]:
    with (directory / filename).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class EvidenceLedger:
    """Maintains an ordered, auditable collection of factual findings."""

    def __init__(self):
        self._items: list[EvidenceItem] = []

    def log(self, source: str, finding: str, reference: str | None = None) -> EvidenceItem:
        ev_id = f"EV-{len(self._items) + 1:03d}"
        item = EvidenceItem(evidence_id=ev_id, source=source, finding=finding, reference=reference)
        self._items.append(item)
        return item

    def get_all(self) -> list[EvidenceItem]:
        return list(self._items)


class ProcurementToolbox:
    """Request-scoped execution suite providing 5 deterministic & API tools."""

    def __init__(
        self,
        request_dict: dict,
        telemetry: RunTelemetry,
        data_dir: Path = DATA_DIR,
        risk_fetcher: Callable[[str], dict] | None = None,
    ):
        self.request = request_dict
        self.telemetry = telemetry
        self.data_dir = data_dir
        self.risk_fetcher = risk_fetcher or get_vendor_risk
        self.ledger = EvidenceLedger()
        self.cache: dict[str, Any] = {}

    def execute(self, tool_name: str) -> dict[str, Any]:
        if tool_name in self.cache:
            return self.cache[tool_name]

        if not hasattr(self, tool_name):
            raise ValueError(f"Unknown tool requested: {tool_name}")

        start_time = time.perf_counter()
        self.telemetry.tool_calls += 1
        self.telemetry.tool_names.append(tool_name)

        try:
            result = getattr(self, tool_name)()
        except Exception as exc:
            result = {"status": "error", "error_type": type(exc).__name__, "message": str(exc)}
            self.ledger.log(
                source=tool_name,
                finding=f"Tool execution failed: {type(exc).__name__}. Favorable status was not assumed.",
                reference=tool_name,
            )

        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        self.telemetry.execution_trace.append({"tool": tool_name, "status": result.get("status", "ok"), "latency_ms": elapsed})
        self.cache[tool_name] = result
        return result

    def requester_budget(self) -> dict[str, Any]:
        employees = read_csv_records("employees.csv", self.data_dir)
        budgets = read_csv_records("department_budgets.csv", self.data_dir)

        emp = next((e for e in employees if e["employee_id"] == self.request.get("requester_id")), None)
        mgr = next((e for e in employees if emp and e["employee_id"] == emp.get("manager_id")), None) if emp else None
        budget = next((b for b in budgets if emp and b["department"] == emp.get("department")), None) if emp else None

        if emp:
            self.ledger.log(
                source="requester_budget",
                finding=f"Requester {emp['name']} belongs to {emp['department']}; manager: {mgr['name'] if mgr else 'None'}.",
                reference=f"employees.csv:{emp['employee_id']}",
            )
        else:
            self.ledger.log(
                source="requester_budget",
                finding="Requester ID could not be resolved in the corporate employee registry.",
                reference="employees.csv",
            )

        if budget:
            avail = float(budget["available_usd"])
            cost = self.request.get("annual_cost_usd")
            cost_str = f"${cost:,.2f}" if cost is not None else "unknown"
            self.ledger.log(
                source="requester_budget",
                finding=f"{budget['department']} department software budget: ${avail:,.2f} available. Requested amount: {cost_str}.",
                reference=f"department_budgets.csv:{budget['department']}",
            )

        return {"status": "ok", "employee": emp, "manager": mgr, "budget": budget}

    def software_catalog(self) -> dict[str, Any]:
        catalog = read_csv_records("software_catalog.csv", self.data_dir)
        req_product = (self.request.get("product_name") or "").strip().lower()
        req_vendor = (self.request.get("vendor_name") or "").strip().lower()
        req_category = (self.request.get("category") or "").strip().lower()

        matches = []
        for item in catalog:
            reasons = []
            if req_product and item["product_name"].lower() == req_product:
                reasons.append("exact_product")
            if req_vendor and item["vendor_name"].lower() == req_vendor:
                reasons.append("same_vendor")
            if req_category and item["category"].lower() == req_category:
                reasons.append("same_category")

            if reasons and item["status"].startswith("Approved"):
                matches.append({**item, "match_reasons": reasons})
                self.ledger.log(
                    source="software_catalog",
                    finding=f"Found existing approved software: {item['product_name']} (ID: {item['software_id']}) under {item['category']} scope {item['scope']} with {item['licensed_seats']} seats.",
                    reference=f"software_catalog.csv:{item['software_id']}",
                )

        if not matches:
            self.ledger.log(
                source="software_catalog",
                finding="No direct active software catalog overlaps identified.",
                reference="software_catalog.csv",
            )

        return {"status": "ok", "matches": matches}

    def vendor_registry(self) -> dict[str, Any]:
        vendors = read_csv_records("vendors.csv", self.data_dir)
        purchases = read_csv_records("purchase_history.csv", self.data_dir)
        target_vendor = (self.request.get("vendor_name") or "").strip().lower()

        vendor = next((v for v in vendors if v["vendor_name"].lower() == target_vendor), None)
        past_orders = [p for p in purchases if p["vendor_name"].lower() == target_vendor]

        if vendor:
            self.ledger.log(
                source="vendor_registry",
                finding=f"Vendor registry record for '{vendor['vendor_name']}': Status={vendor['procurement_status']}, Security={vendor['security_status']}, Review Date={vendor['security_review_date'] or 'None'}, Legal Terms={vendor['legal_terms_status']}.",
                reference=f"vendors.csv:{vendor['vendor_id']}",
            )
        else:
            self.ledger.log(
                source="vendor_registry",
                finding=f"Vendor '{self.request.get('vendor_name')}' is not registered in the procurement database.",
                reference="vendors.csv",
            )

        for po in past_orders:
            self.ledger.log(
                source="vendor_registry",
                finding=f"Historical purchase: {po['product_name']} for {po['department']} (${float(po['annual_amount_usd']):,.2f}, Status: {po['status']}).",
                reference=f"purchase_history.csv:{po['purchase_id']}",
            )

        return {"status": "ok", "vendor": vendor, "purchase_history": past_orders}

    def vendor_risk(self) -> dict[str, Any]:
        vendor_name = (self.request.get("vendor_name") or "").strip()
        if not vendor_name:
            raise ValueError("Cannot query vendor risk API without vendor name")

        assessment = self.risk_fetcher(vendor_name)
        self.ledger.log(
            source="vendor_risk",
            finding=f"Vendor Risk API for {vendor_name}: Security Status='{assessment.get('security_review_status')}', Last Review='{assessment.get('last_review_date')}', Risk='{assessment.get('risk_level')}', Stores Outside Region={assessment.get('stores_data_outside_region')}.",
            reference=f"GET /vendor-risk/{vendor_name}",
        )
        return {"status": "ok", "assessment": assessment}

    def policy_check(self) -> dict[str, Any]:
        # Pre-requisite: ensure all foundational tools have executed
        for prereq in ["requester_budget", "software_catalog", "vendor_registry", "vendor_risk"]:
            self.execute(prereq)

        evaluation = PolicyEngine.evaluate(self.request, self.cache)
        for reason in evaluation["audit_reasons"]:
            self.ledger.log(source="policy_check", finding=reason, reference="data/procurement_policy.md")

        return {"status": "ok", "evaluation": evaluation}

    def gather_all(self) -> dict[str, Any]:
        self.execute("policy_check")
        return self.cache