# app.py
# Floww – AI-powered Deal Workflow Generator (Next-Level Mermaid)
# ================================================================
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
default_import_openai
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

# ── Sidebar Inputs ───────────────────────────────────────────
st.sidebar.header("Input Options")
company     = st.sidebar.text_input("Company name", "Acme Corp")
industry    = st.sidebar.selectbox("Industry", ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
persona     = st.sidebar.selectbox("Persona", ["Enterprise AE", "SMB SDR", "Partner Manager"])
crm_file    = st.sidebar.file_uploader("Upload CRM CSV (lead,stage,probability)", type="csv")
competitor  = st.sidebar.selectbox("Benchmark vs.", ["None", "Visa", "Stripe", "Amex"])
pptx_export = st.sidebar.checkbox("Enable PPTX Export", True)

# ── Generate Workflow ─────────────────────────────────────────
if st.sidebar.button("Generate Next-Level Workflow"):
    # 1️⃣ Generate JSON workflow via AI
    system_msg = (
        "You are an enterprise sales consultant. "
        "Output ONLY valid JSON with exactly one key 'workflow', an array of {stage, tip} objects."
    )
    user_msg = (
        f"Build a deal-closing workflow for a {persona} at {company}, industry={industry}. "
        "Provide each stage and a concise best-practice tip."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
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

    # 2️⃣ Generate Mermaid code via AI
    mermaid_system = (
        "You are a code generator. "
        "Generate a Mermaid.js flowchart code snippet only, no explanation."
    )
    mermaid_user = (
        f"Create a Mermaid flowchart for the following stages in order: {stages}. "
        f"Label the chart 'Floww Workflow for {company}'."
    )
    mresp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":mermaid_system},
            {"role":"user","content":mermaid_user},
        ],
        temperature=0.0,
        max_tokens=200,
    )
    mermaid_code = mresp.choices[0].message.content.strip()
    # Strip fences
    mermaid_code = re.sub(r"^```mermaid|```$","", mermaid_code, flags=re.M)

    # Display Mermaid
    st.subheader("AI-Generated Mermaid Diagram Code")
    st.code(mermaid_code, language="")
    st.subheader("Rendered Mermaid Diagram")
    st.markdown(f"```mermaid\n{mermaid_code}\n```", unsafe_allow_html=True)

    # 3️⃣ Competitor Benchmarks
    if competitor != "None":
        bench = {
            "Visa":   ["Prospecting","KYC Check","Regulatory Review"],
            "Stripe": ["API Integration Pilot","Sandbox Testing"],
            "Amex":   ["Regulatory Compliance","Fraud Assessment"],
        }
        st.subheader(f"Benchmark Stages vs {competitor}")
        st.write(bench.get(competitor, []))

    # 4️⃣ Personalized CRM Playbook
    if crm_file:
        df_crm = pd.read_csv(crm_file)
        play = []
        for _, r in df_crm.iterrows():
            data = r.to_dict()
            tip_prompt = f"Given lead data {data}, suggest next-step tip."
            tip_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"user","content":tip_prompt}],
                temperature=0.7,
                max_tokens=100,
            )
            play.append({**data, 'suggestion': tip_resp.choices[0].message.content})
        st.subheader("Personalized Playbook from CRM")
        st.dataframe(pd.DataFrame(play))

    # 5️⃣ PPTX Export
    if pptx_export:
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = f"Floww Playbook: {company}"
        for s in stages:
            sl = prs.slides.add_slide(prs.slide_layouts[1])
            sl.shapes.title.text = s
            sl.placeholders[1].text = tips[s]
        out = io.BytesIO(); prs.save(out); out.seek(0)
        st.download_button("Download PPTX Playbook", out,
                           "floww_playbook.pptx", 
                           "application/vnd.openxmlformats-officedocument.presentationml.presentation")

    # Final Workflow Display
    st.subheader("Workflow Stages & Tips")
    for s in stages:
        st.markdown(f"**{s}** — {tips[s]}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
