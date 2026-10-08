# AI Procurement Request Copilot

An enterprise procurement copilot designed to ingest software and service purchase requests, gather grounded evidence using deterministic and external tools, enforce corporate procurement policy guardrails, and generate auditable next-step recommendations while strictly preserving human approval authority.

Built for **FDE Assessment 3**, this repository implements and compares:
1. **Architecture A — Single-Agent Baseline**: An autonomous one-pass agent gathering tool evidence and synthesizing recommendations.
2. **Architecture B — Staged Dual-Agent Pipeline**: A two-stage pipeline separating empirical fact collection (**Intake Investigator**) from governance auditing (**Compliance Reviewer**).

---

## Key Features & Guardrails

* **Preserved Human Authority**: The system cannot autonomously approve purchases, alter department budgets, or accept legal terms. Every recommendation routes to designated human roles with pending sign-off status.
* **Deterministic Policy Engine (`Policy 2026.09`)**: Hardcoded Python logic evaluates spend thresholds, department budget limits, and vendor review expiration against the evaluation reference snapshot date (**2026-09-30**), never the host system clock.
* **Immutable Evidence Ledger**: Tools assign sequential evidence IDs (`EV-001`, `EV-002`, etc.) citing source files, API endpoints, or policy sections. The model cannot hallucinate citations.
* **Adversarial Prompt Isolation**: Business justifications and vendor descriptions are treated strictly as untrusted data. Embedded instructions attempting to bypass approval or claim "CFO-approved" status are flagged (`prompt_injection_detected`) and neutralized.
* **Graceful Degradation**: Outages in external dependencies (e.g., HTTP 503 from the vendor-risk service) are logged explicitly without assuming favorable status, routing the request to manual human verification.

---

## Tool Suite

The copilot provides 5 request-scoped tools:

| Tool | Type | Purpose & Scope |
| :--- | :--- | :--- |
| `requester_budget` | Deterministic | Resolves requester, department, reporting line, and available department software budget. |
| `software_catalog` | Deterministic | Scans approved catalog products for exact, vendor, category, or functional overlaps. |
| `vendor_registry` | Deterministic | Retrieves internal procurement status, security assessment date, and purchase history. |
| `vendor_risk` | HTTP External | Queries the external vendor-risk API; gracefully handles outages and timeouts. |
| `policy_check` | Deterministic | Applies financial spend tiers, PII/infosec rules, and generates required approvals. |

---

## Architecture Comparison

### Architecture A: Single-Agent Baseline
* Gathers evidence across all tools in a single context window.
* Evaluates policy findings and generates the `ProcurementDecision` payload in a single pass.
* Minimal latency, but prone to mixing business persuasion with policy constraints.

### Architecture B: Dual-Stage Pipeline
* **Stage 1 (Intake Investigator)**: Gathers evidence, assesses functional gaps, and evaluates whether catalog software satisfies the stated need.
* **Stage 2 (Compliance Reviewer)**: Receives the Stage 1 findings in a clean context, audits the request against Policy 2026.09 rules, and enforces mandatory approval gates.
* Provides clear audit trails and clean separation between empirical fact-finding and governance adjudication.

---

## Local Setup & Quick Start

### 1. Environment Preparation
Ensure Python 3.11+ is installed.

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
python -m pip install -r requirements.txt

```

### 2. Verify Pre-Flight Checks

Run the starter integrity suite to verify data consistency, Pydantic contracts, and the mock API:

```bash
python verify_setup.py

```

*Expected output: `PRE-FLIGHT PASSED*`

### 3. Start Local Services

Launch the vendor-risk mock API and the Streamlit procurement workbench concurrently:

```bash
python run_local.py

```

* **Vendor Risk API**: `http://127.0.0.1:8001`
* **Streamlit Workbench**: `http://127.0.0.1:8501`

---

## Evaluation & Testing

Run all automated unit tests and evaluation harnesses from an active virtual environment:

```bash
# Run unit and regression tests
python -m pytest tests/ -v

# Run the 6 public assessment cases on Architecture A
python evals/run_public_evals.py --architecture single

# Run the 6 public assessment cases on Architecture B
python evals/run_public_evals.py --architecture staged

# Run comparative evaluation summary
python evals/compare.py

```

---

## Project Structure

```text
├── data/                       # Synthetic business data & procurement policy (2026.09)
├── evals/
│   ├── public_cases.json       # 6 official public evaluation test scenarios
│   ├── run_public_evals.py     # Public evaluation harness
│   └── compare.py              # Comparative architecture benchmark runner
├── mock_api/                   # FastAPI mock vendor risk service
├── src/
│   ├── contracts.py            # Pydantic V2 data contracts (ProcurementDecision)
│   ├── data_access.py          # CSV and JSON loaders
│   ├── policy_engine.py        # Deterministic Policy 2026.09 business rules
│   ├── tools.py                # Class-based tool suite & EvidenceLedger
│   ├── agents.py               # Single agent & dual-stage pipeline implementations
│   ├── solution.py             # Public assessment handle_request adapter
│   └── vendor_client.py        # HTTP client for mock risk API
├── templates/
│   └── architecture_decision.md# Decision memo (< 500 words)
├── tests/
│   ├── test_data_integrity.py  # Dataset integrity validation
│   ├── test_mock_api.py        # Mock vendor-risk API tests
│   └── test_solution.py        # Comprehensive unit tests & edge cases
├── app.py                      # Interactive Streamlit workbench UI
├── run_local.py                # Dual-service orchestrator
├── verify_setup.py             # Starter pack pre-flight check
└── requirements.txt            # Pinned Python package dependencies