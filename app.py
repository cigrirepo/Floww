# app.py
# Floww – AI-powered Mermaid Diagram Generator
# =============================================

import os
import re
import streamlit as st
from openai import OpenAI

# ── UI Config ─────────────────────────────────────────────────
st.set_page_config(page_title="Floww Mermaid", layout="wide")
st.title("Floww – AI-powered Mermaid Diagram Generator")
st.caption("Generate and render advanced Mermaid.js flowcharts via OpenAI")

# ── OpenAI Client ───────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY environment variable.")
    st.stop()
client = OpenAI(api_key=api_key)

# ── Sidebar Inputs ──────────────────────────────────────────
st.sidebar.header("Mermaid Diagram Options")
company     = st.sidebar.text_input("Company name", "Acme Corp")
persona     = st.sidebar.selectbox("Persona", ["Enterprise AE", "SMB SDR", "Partner Manager"])
stages_text = st.sidebar.text_area(
    "Workflow stages (comma-separated)",
    "prospecting, qualification, research, discovery call, proposal, negotiation, onboarding, post-sale engagement, upsell"
)

# ── Mermaid Prompt Templates ─────────────────────────────────
mermaid_sys = (
    "You are a sales operations architect and diagram expert. "
    "Output **only** a Mermaid.js flowchart snippet—no markdown fences or commentary—meeting these requirements:\n"
    "1. Title the chart \"Floww Workflow for {company}\".\n"
    "2. Group the workflow into three subgraphs:\n"
    "   - Pre-Sales: prospecting, qualification, research\n"
    "   - Sales: discovery call, proposal, negotiation\n"
    "   - Post-Sales: onboarding, post-sale engagement, upsell\n"
    "3. Use swimlanes to distinguish roles: SDR (Pre-Sales), AE (Sales), CSM (Post-Sales).\n"
    "4. Label each arrow with the key action (e.g., Outbound Email, Demo Call, Contract Review).\n"
    "5. Lay out the chart top-to-bottom.\n"
    "Keep it concise."
).format(company=company)

# ── Generate Mermaid Diagram ─────────────────────────────────
if st.sidebar.button("Generate Mermaid Diagram"):
    # Prepare the user message
    mermaid_usr = f"Here are the stages: {stages_text}."

    # Call OpenAI
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",  "content": mermaid_sys},
            {"role": "user",    "content": mermaid_usr},
        ],
        temperature=0.0,
        max_tokens=300,
    )

    # Extract and clean up the Mermaid code
    raw = resp.choices[0].message.content.strip()
    mermaid_code = re.sub(r"^```mermaid|```$", "", raw, flags=re.M)

    # Display
    st.subheader("Mermaid Diagram Code")
    st.code(mermaid_code, language="")

    st.subheader("Rendered Mermaid Diagram")
    st.markdown(f"```mermaid\n{mermaid_code}\n```", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
