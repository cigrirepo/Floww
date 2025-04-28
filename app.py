# app.py
# Floww – AI-powered Deal Workflow Generator (Next-Level Mermaid)
# ===============================================================
# Uses AI to generate JSON workflow, Mermaid code, personalized playbooks,
# competitor benchmarks, PPTX export, and role-tailored diagrams.

import io
import os
import re
import json
from typing import List

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pptx import Presentation

# ── UI Config ─────────────────────────────────────────────────
st.set_page_config(page_title="Floww Advanced", layout="wide")
st.title("Floww Advanced")
st.caption("AI-powered deal workflows + AI-generated Mermaid diagrams + playbooks")

# ── OpenAI Client ───────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY environment variable.")
    st.stop()
client = OpenAI(api_key=api_key)

# ── Pydantic Models ─────────────────────────────────────────
class StageModel(BaseModel):
    stage: str
    tip:   str

class WorkflowModel(BaseModel):
    workflow: List[StageModel]

# ── Sidebar Inputs ──────────────────────────────────────────
st.sidebar.header("Input Options")
company     = st.sidebar.text_input("Company name", "Acme Corp")
industry    = st.sidebar.selectbox("Industry", ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
persona     = st.sidebar.selectbox("Persona", ["Enterprise AE", "SMB SDR", "Partner Manager"])
crm_file    = st.sidebar.file_uploader("Upload CRM CSV (lead,stage,probability)", type="csv")
competitor  = st.sidebar.selectbox("Benchmark vs.", ["None", "Visa", "Stripe", "Amex"])
pptx_export = st.sidebar.checkbox("Enable PPTX Export", True)

# ── Generate Next-Level Workflow ────────────────────────────
if st.sidebar.button("Generate Next-Level Workflow"):
    # 1️⃣ Generate JSON workflow via AI
    system_msg = (
        "You are an enterprise sales consultant. "
        "Respond with ONLY valid JSON with exactly one key 'workflow', "
        "an array of {stage, tip} objects."
    )
    user_msg = (
        f"Build a deal-closing workflow for a {persona} at {company}, industry={industry}. "
        "Provide each stage and a concise best-practice tip."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system", "content":system_msg},
            {"role":"user",   "content":user_msg},
        ],
        temperature=0.0,
        max_tokens=600,
    )
    raw_json = resp.choices[0].message.content

    # Extract JSON
    m = re.search(r"\{.*\}", raw_json, re.S)
    if not m:
        st.error("Failed to extract JSON. Raw AI output:")
        st.code(raw_json, language="json")
        st.stop()
    json_str = m.group(0)

    # Parse JSON
    try:
        wf = WorkflowModel.parse_raw(json_str)
    except ValidationError as e:
        st.error("JSON validation error. Extracted JSON:")
        st.code(json_str, language="json")
        st.error(str(e))
        st.stop()

    stages = [s.stage for s in wf.workflow]
    tips   = {s.stage: s.tip for s in wf.workflow}

       # ── Generate Advanced Mermaid Diagram via AI ─────────────────────────
    mermaid_sys = """
You are a sales operations architect and diagram expert. Output **only** a Mermaid.js flowchart snippet—no markdown fences, no commentary—meeting these requirements:

1. Title the chart “Floww Workflow for {company}”.
2. Group the workflow into three subgraphs:
   - Pre-Sales: prospecting, qualification, research
   - Sales: discovery call, proposal, negotiation
   - Post-Sales: onboarding, post-sale engagement, upsell
3. Use swimlanes to distinguish roles: SDR (Pre-Sales), AE (Sales), CSM (Post-Sales).
4. Label each arrow with the key action (e.g., “Outbound Email”, “Demo Call”, “Contract Review”).
5. Lay out the chart top-to-bottom.

Keep it DRY and as concise as possible.
"""

    mermaid_usr = f"Here are the stages: {stages}."

    mresp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",  "content": mermaid_sys.strip().format(company=company)},
            {"role": "user",    "content": mermaid_usr},
        ],
        temperature=0.0,
        max_tokens=300,
    )
    mermaid_code = mresp.choices[0].message.content.strip()
    # strip any backticks
    mermaid_code = re.sub(r"^```mermaid|```$", "", mermaid_code, flags=re.M)

    st.subheader("AI-Generated Advanced Mermaid Diagram Code")
    st.code(mermaid_code, language="")
    st.subheader("Rendered Advanced Mermaid Diagram")
    st.markdown(f"```mermaid\n{mermaid_code}\n```", unsafe_allow_html=True)

    # 3️⃣ Competitor Benchmarks
    if competitor != "None":
        bench = {
            "Visa":   ["Prospecting", "KYC Check", "Regulatory Review"],
            "Stripe": ["API Integration Pilot", "Sandbox Testing"],
            "Amex":   ["Regulatory Compliance", "Fraud Assessment"],
        }
        st.subheader(f"Benchmark Stages vs {competitor}")
        st.write(bench.get(competitor, []))

    # 4️⃣ Personalized Playbook from CRM CSV
    if crm_file:
        df = pd.read_csv(crm_file)
        playbook = []
        for _, row in df.iterrows():
            data = row.to_dict()
            tip_prompt = f"Lead data: {data}. Suggest the next-step tip."
            tip_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"user","content":tip_prompt}],
                temperature=0.7,
                max_tokens=100,
            )
            playbook.append({**data, "suggestion": tip_resp.choices[0].message.content})
        st.subheader("Personalized Playbook from CRM")
        st.dataframe(pd.DataFrame(playbook))

    # 5️⃣ PPTX Export
    if pptx_export:
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = f"Floww Playbook: {company}"
        for s in stages:
            sl = prs.slides.add_slide(prs.slide_layouts[1])
            sl.shapes.title.text = s
            sl.placeholders[1].text = tips[s]
        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        st.download_button(
            "Download PPTX Playbook",
            buf,
            "floww_playbook.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )

    # Final Workflow Display
    st.subheader("Workflow Stages & Tips")
    for s in stages:
        st.markdown(f"**{s}** — {tips[s]}")

# ── Footer ─────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
