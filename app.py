from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from src.contracts import ProcurementDecision, PurchaseRequestInput
from src.data_access import load_employees, load_requests
from src.solution import analyze_request

ROOT = Path(__file__).resolve().parent
REQUESTS_POOL = {r["request_id"]: r for r in load_requests()}
EMPLOYEES = load_employees().to_dict(orient="records")

st.set_page_config(page_title="Procure Copilot | FDE Assessment 3", layout="wide", page_icon="⚖️")

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }
    .badge-pending { background: #fef3c7; color: #92400e; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; }
    .badge-approved { background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 0.8rem; }
    .stButton>button { width: 100%; border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚖️ AI Procurement Request Copilot")
st.caption("FDE Assessment 3 • Automated Evidence Gathering & Policy Compliance Engine • Snapshot: 2026-09-30")

# Sidebar Configuration
st.sidebar.header("⚙️ Request Selection")
options = ["-- Create New Custom Request --"] + [f"{r['request_id']} - {r['product_name']}" for r in REQUESTS_POOL.values()]
chosen = st.sidebar.selectbox("Load Request Template", options)

arch_choice = st.sidebar.radio(
    "Orchestration Architecture",
    ["single", "staged"],
    format_func=lambda x: "Architecture A: Single Agent" if x == "single" else "Architecture B: Staged (2 Agents)",
)

st.sidebar.divider()
st.sidebar.info("Advisory Safeguard: Copilot recommendations are non-autonomous. All purchasing decisions require verified human signoff.")

# Request Form Population
if chosen == "-- Create New Custom Request --":
    active_req = {
        "request_id": "REQ-CUSTOM",
        "requester_id": "E001",
        "product_name": "",
        "vendor_name": "",
        "category": "Project Management",
        "annual_cost_usd": 15000.0,
        "user_count": 10,
        "business_justification": "",
        "data_access_level": "internal_documents",
        "requested_integrations": [],
        "urgency": "normal",
    }
else:
    req_id = chosen.split(" - ")[0]
    active_req = REQUESTS_POOL[req_id]

col_left, col_right = st.columns([1.1, 0.9], gap="large")

with col_left:
    st.subheader("📝 Request Parameters")
    with st.form("request_intake_form"):
        r_id = st.text_input("Request ID", value=active_req["request_id"], disabled=True)
        emp_options = {e["employee_id"]: f"{e['name']} ({e['department']})" for e in EMPLOYEES}
        requester_id = st.selectbox(
            "Requester",
            options=list(emp_options.keys()),
            index=list(emp_options.keys()).index(active_req.get("requester_id", "E001")),
            format_func=lambda k: emp_options[k],
        )

        c1, c2 = st.columns(2)
        with c1:
            product_name = st.text_input("Product Name", value=active_req.get("product_name") or "")
            category = st.text_input("Category", value=active_req.get("category") or "")
            cost_val = active_req.get("annual_cost_usd")
            annual_cost = st.number_input("Annual Cost (USD)", value=float(cost_val) if cost_val is not None else 0.0, step=100.0)
        with c2:
            vendor_name = st.text_input("Vendor Name", value=active_req.get("vendor_name") or "")
            users_val = active_req.get("user_count")
            user_count = st.number_input("Licensed Users", value=int(users_val) if users_val is not None else 1, step=1)
            urgency = st.selectbox("Urgency", ["low", "normal", "high", "urgent"], index=["low", "normal", "high", "urgent"].index(active_req.get("urgency", "normal")))

        justification = st.text_area("Business Justification", value=active_req.get("business_justification") or "")

        data_levels = [
            "none", "internal_documents", "internal_marketing", "source_code",
            "production_telemetry", "cloud_account", "confidential_documents",
            "employee_pii", "customer_pii", "unknown"
        ]
        curr_dl = active_req.get("data_access_level", "internal_documents")
        dl_idx = data_levels.index(curr_dl) if curr_dl in data_levels else 0
        data_access = st.selectbox("Intended Data Access Level", data_levels, index=dl_idx)

        integrations_str = st.text_input("Integrations (comma-separated)", value=", ".join(active_req.get("requested_integrations") or []))

        submitted = st.form_submit_button("⚡ Run Compliance & Procurement Analysis", type="primary")

with col_right:
    st.subheader("🔍 Copilot Recommendation & Audit")

    if submitted or "last_decision" in st.session_state:
        if submitted:
            integrations_list = [i.strip() for i in integrations_str.split(",") if i.strip()]
            payload = {
                "request_id": r_id,
                "requester_id": requester_id,
                "product_name": product_name,
                "vendor_name": vendor_name,
                "category": category,
                "annual_cost_usd": float(annual_cost) if annual_cost > 0 else None,
                "user_count": int(user_count) if user_count > 0 else None,
                "business_justification": justification,
                "data_access_level": data_access,
                "requested_integrations": integrations_list,
                "urgency": urgency,
            }
            with st.spinner("Analyzing request against Policy 2026.09..."):
                st.session_state["last_decision"] = analyze_request(payload, architecture=arch_choice, mode="offline")

        dec: ProcurementDecision = st.session_state["last_decision"]

        st.success(f"**Recommendation**: {dec.recommendation}")
        st.markdown(f"**Next Operational Step**: {dec.next_step}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Latency", f"{dec.telemetry.latency_ms:.1f} ms" if dec.telemetry else "N/A")
        m2.metric("Tools Invoked", dec.telemetry.tool_calls if dec.telemetry else 0)
        m3.metric("LLM Invocations", dec.telemetry.llm_calls if dec.telemetry else 0)
        m4.metric("Authority", "Human Guarded")

        tab_approvals, tab_risks, tab_evidence, tab_trace = st.tabs(["👥 Approvals", "⚠️ Risks & Missing Info", "📋 Evidence Ledger", "🔬 Audit Trace"])

        with tab_approvals:
            st.markdown("#### Required Human Approval Gates")
            for role in dec.required_approvals:
                st.markdown(f"- **{role}** <span class='badge-pending'>SIGN-OFF PENDING</span>", unsafe_allow_html=True)

        with tab_risks:
            st.markdown("#### Identified Policy & Security Risk Flags")
            if dec.risk_flags:
                for rf in dec.risk_flags:
                    st.error(f"🚩 `{rf}`")
            else:
                st.info("No compliance or risk flags identified.")

            st.markdown("#### Missing / Unverified Information")
            if dec.missing_information:
                for mi in dec.missing_information:
                    st.warning(f"❓ {mi}")
            else:
                st.info("All required request fields are satisfied.")

        with tab_evidence:
            st.markdown("#### Grounded Evidence Ledger")
            for ev in dec.evidence:
                with st.expander(f"[{ev.evidence_id or 'EV'}] {ev.source}"):
                    st.write(ev.finding)
                    if ev.reference:
                        st.caption(f"Citation: `{ev.reference}`")

        with tab_trace:
            st.markdown("#### Raw Output Contract")
            st.json(dec.model_dump())

        st.download_button(
            label="📥 Export Human Review Package (JSON)",
            data=dec.model_dump_json(indent=2),
            file_name=f"procurement_handoff_{dec.request_id}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.info("Select a request scenario on the left and click **Run Compliance & Procurement Analysis**.")