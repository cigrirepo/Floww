# app.py
# Floww – AI-powered Deal Workflow Generator (v2 with advanced features)
# Includes: CSV upload playbook, competitor templates, PPTX export, persona-specific tips
# Robust JSON extraction via regex to prevent parse errors

import io
import os
import re
import json
from typing import List
import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from pptx import Presentation

# ── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Floww Advanced", layout="wide")
st.title("Floww Advanced")
st.caption("Deal workflows + personalized playbooks, competitor benchmarks, PPTX export & personas")

# ── AUTH ───────────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY")
    st.stop()
client = OpenAI(api_key=api_key)

# ── Pydantic models ────────────────────────────────────
class StageModel(BaseModel):
    stage: str
    tip:   str

class WorkflowModel(BaseModel):
    workflow: List[StageModel]

# ── SIDEBAR INPUTS ─────────────────────────────────────
st.sidebar.header("Input options")
company     = st.sidebar.text_input("Company name", "Acme Corp")
industry    = st.sidebar.selectbox("Industry", ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
persona     = st.sidebar.selectbox("Persona", ["Enterprise AE", "SMB SDR", "Partner Manager"])
crm_file    = st.sidebar.file_uploader("Upload CRM CSV (lead,stage,probability)", type="csv")
competitor  = st.sidebar.selectbox("Benchmark vs.", ["None", "Visa", "Stripe", "Amex"])
pptx_export = st.sidebar.checkbox("Enable PPTX Export", True)

# ── GENERATE WORKFLOW ─────────────────────────────────
if st.sidebar.button("Generate Advanced Workflow"):

    # 1️⃣ Base AI prompt for JSON-only response
    system_msg = (
        "You are an enterprise sales consultant. "
        "Respond with ONLY valid JSON—no markdown, no explanation. "
        "Use this schema: {\"workflow\":[{\"stage\":\"...\",\"tip\":\"...\"},...]}"
    )
    user_msg = (
        f"Persona: {persona}. Company: {company}. Industry: {industry}. "
        "Return a deal-closing workflow in the JSON format specified."
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg}
        ],
        temperature=0.0,
        max_tokens=800,
    )
    raw_output = resp.choices[0].message.content

    # 2️⃣ Extract JSON object using regex
    match = re.search(r"\{.*\}", raw_output, re.S)
    if not match:
        st.error("Could not find JSON object in AI response. Raw output:")
        st.code(raw_output, language="json")
        st.stop()
    json_str = match.group(0)

    # 3️⃣ Parse JSON via Pydantic
    try:
        wf = WorkflowModel.parse_raw(json_str)
    except ValidationError as e:
        st.error("JSON schema validation failed. Extracted JSON:")
        st.code(json_str, language="json")
        st.error(str(e))
        st.stop()

    stages = [step.stage for step in wf.workflow]
    tips   = {step.stage: step.tip for step in wf.workflow}

    # ── Competitor Benchmark Templates ─────────────────────────
    if competitor != "None":
        bench = {
            "Visa":   ["Prospecting", "KYC Check", "Regulatory Review"],
            "Stripe": ["API Integration Pilot", "Sandbox Testing"],
            "Amex":   ["Regulatory Compliance", "Fraud Assessment"]
        }
        st.subheader(f"Benchmark Stages vs {competitor}")
        st.write(bench.get(competitor, []))

    # ── Personalized Playbook from CRM CSV ──────────────────
    if crm_file:
        df_crm = pd.read_csv(crm_file)
        playbook = []
        for _, row in df_crm.iterrows():
            lead_data = row.to_dict()
            tip_prompt = f"Lead data: {lead_data}. Suggest the next-step tip."
            tip_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": tip_prompt}],
                temperature=0.7,
                max_tokens=200
            )
            suggestion = tip_resp.choices[0].message.content
            playbook.append({**lead_data, "suggestion": suggestion})
        st.subheader("Personalized Playbook from CRM")
        st.dataframe(pd.DataFrame(playbook))

    # ── PPTX Export ─────────────────────────────────────────
    if pptx_export:
        prs = Presentation()
        # Title slide
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = f"Floww Playbook: {company}"
        # One slide per stage
        for s in stages:
            sl = prs.slides.add_slide(prs.slide_layouts[1])
            sl.shapes.title.text = s
            body = sl.shapes.placeholders[1].text_frame
            body.text = tips[s]
        pptx_buf = io.BytesIO()
        prs.save(pptx_buf)
        pptx_buf.seek(0)
        st.download_button(
            "Download PPTX Playbook",
            pptx_buf,
            "floww_playbook.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    # ── Display Core Workflow ───────────────────────────────
    st.subheader("Workflow Stages & Tips")
    for s in stages:
        st.markdown(f"**{s}** — {tips[s]}")

# ── FOOTER ───────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
