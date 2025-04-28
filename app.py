# app.py
# Floww – AI-powered Deal Workflow & Proposal Generator
# ======================================================
# Features:
# - Real-company data via stock ticker or website (Clearbit/YFinance)
# - Two-pane layout: Workflow & Proposal
# - AI-driven JSON workflows & advanced Mermaid diagrams with theming
# - Editable JSON for live diagram re-render
# - Built-in proposal generator with PDF export
# - Industry presets and Mermaid theme injection

import io
import os
import re
import json
from datetime import date
from typing import List, Dict

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pptx import Presentation
import yfinance as yf
import requests

# ── UI Config ─────────────────────────────────────────────
st.set_page_config(page_title="Floww Advanced", layout="wide")
st.title("Floww Advanced")
st.caption("AI-driven workflows, diagrams & proposals tailored to real companies")

# ── Clients & API Keys ─────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
clearbit_key = os.getenv("CLEARBIT_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY")
    st.stop()
client = OpenAI(api_key=api_key)

# ── Pydantic Models ───────────────────────────────────────
class StageModel(BaseModel): stage: str; tip: str
class WorkflowModel(BaseModel): workflow: List[StageModel]
class ProposalModel(BaseModel):
    title: str
    executive_summary: str
    background: str
    solution_overview: str
    deliverables: List[str]
    pricing: List[Dict[str,int]]
    next_steps: str

# ── Sidebar Inputs ────────────────────────────────────────
st.sidebar.header("Company Data & Presets")
company       = st.sidebar.text_input("Company name", "Acme Corp")
website_url   = st.sidebar.text_input("Company website (optional)")
ticker        = st.sidebar.text_input("Stock ticker (optional)")
industry      = st.sidebar.selectbox("Industry",
                    ["Fintech","SaaS","Retail","Healthcare","Other"])
preset_desc = {
    "Fintech": "a regulated financial services provider",
    "SaaS":     "a fast-growing software-as-a-service company",
    "Retail":   "a global retail chain",
    "Healthcare": "a healthcare technology provider",
    "Other":    "a leading enterprise"
}[industry]

# Additional options
persona       = st.sidebar.selectbox("Persona", ["Enterprise AE","SMB SDR","Partner Manager"])
crm_file      = st.sidebar.file_uploader("Upload CRM CSV (lead,stage,probability)", type="csv")
competitor    = st.sidebar.selectbox("Benchmark vs.",["None","Visa","Stripe","Amex"])
pptx_export   = st.sidebar.checkbox("Enable PPTX Export", True)

# Fetch real-company info
description = preset_desc
market_cap  = None
if ticker:
    try:
        info = yf.Ticker(ticker).info
        description = info.get("longBusinessSummary", description)
        cap = info.get("marketCap")
        market_cap = f"${cap:,.0f}" if cap else None
    except:
        pass
elif website_url and clearbit_key:
    try:
        resp = requests.get(
            f"https://company.clearbit.com/v1/domains/find?domain={website_url}",
            headers={"Authorization": f"Bearer {clearbit_key}"}
        )
        j = resp.json()
        description = j.get("description", description)
    except:
        pass

# ── Two-pane layout ───────────────────────────────────────
tab1, tab2 = st.tabs(["Workflow","Proposal"])

with tab1:
    # Generate JSON Workflow
    if st.button("Generate Workflow", key="wf"):
        system = (
            "You are an enterprise sales consultant. "
            "Output ONLY valid JSON: {'workflow':[{'stage':'','tip':''}]}"
        )
        prompt = (
            f"Build a deal workflow for a {persona} at {company}, {description}. "
            f"Industry: {industry}. Market cap: {market_cap or 'N/A'}."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},
                      {"role":"user","content":prompt}],
            temperature=0.0, max_tokens=600
        )
        raw = resp.choices[0].message.content
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            st.error("Failed to extract JSON") ; st.code(raw) ; st.stop()
        js = m.group(0)
        try:
            wf = WorkflowModel.parse_raw(js)
        except ValidationError as e:
            st.error("JSON invalid") ; st.code(js) ; st.error(str(e)) ; st.stop()
        stages = [s.stage for s in wf.workflow]
        tips   = {s.stage:s.tip for s in wf.workflow}
        st.session_state['wf_json'] = js
        st.session_state['stages'] = stages
        st.session_state['tips'] = tips
    # JSON editor
    if 'wf_json' in st.session_state:
        st.subheader("Edit Workflow JSON")
        js_edit = st.text_area("JSON", st.session_state['wf_json'], height=200)
        if st.button("Re-Render Diagram", key="rerender"):
            try:
                wf = WorkflowModel.parse_raw(js_edit)
                stages = [s.stage for s in wf.workflow]; tips = {s.stage:s.tip for s in wf.workflow}
                st.session_state['stages'] = stages; st.session_state['tips'] = tips
                st.session_state['wf_json'] = js_edit
            except:
                st.error("Invalid JSON")
    # Mermaid theming + AI code generation
    if 'stages' in st.session_state:
        st.subheader("AI-Generated Mermaid Diagram")
        theme = "%%{init:{'themeVariables':{'primaryColor':'#00ADEF','lineColor':'#888'}}}%%\n"
        sys2 = "You are a diagram expert. Output a concise Mermaid flowchart only."
        usr2 = f"Stages: {st.session_state['stages']} for {company}."
        m2 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys2},{"role":"user","content":usr2}],
            temperature=0.0, max_tokens=200
        ).choices[0].message.content
        mc = re.sub(r"^```(?:mermaid)?|```$","",m2,flags=re.M)
        code = theme + mc
        st.code(code)
        st.markdown(f"```mermaid\n{code}\n```", unsafe_allow_html=True)

with tab2:
    st.subheader("Generate Proposal")
    client_name  = st.text_input("Proposal for (client)")
    prop_date    = st.date_input("Date", date.today())
    deliverables = st.text_area("Key deliverables (one per line)")
    pricing      = st.text_area("Pricing as JSON list", "[{\"item\":\"Service\",\"price\":10000}]")
    if st.button("Generate Proposal", key="prop"):
        sys_p = (
            "You are an expert sales engineer. "
            "Output valid JSON with: title, executive_summary, background, solution_overview, deliverables, pricing, next_steps."
        )
        usr_p = (
            f"Client: {client_name}. Date: {prop_date}. Company: {company}. "
            f"Deliverables: {deliverables.splitlines()}. Pricing: {pricing}."
        )
        rp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys_p},{"role":"user","content":usr_p}],
            temperature=0.3, max_tokens=600
        ).choices[0].message.content
        try:
            prop = json.loads(rp)
        except:
            st.error("Invalid JSON from AI") ; st.code(rp) ; st.stop()
        st.markdown(f"## {prop['title']}")
        st.markdown(f"**Executive Summary**\n{prop['executive_summary']}")
        st.markdown(f"**Background**\n{prop['background']}")
        st.markdown(f"**Solution Overview**\n{prop['solution_overview']}")
        st.markdown(f"**Next Steps**\n{prop['next_steps']}")
        # PDF export
        buf = io.BytesIO(); c = canvas.Canvas(buf,pagesize=letter); w,h=letter
        y=h-40; c.setFont('Helvetica-Bold',14); c.drawString(40,y,prop['title']); y-=30
        c.setFont('Helvetica',12)
        for sec in ['executive_summary','background','solution_overview','next_steps']:
            text = prop.get(sec,'')
            for line in text.split('\n'):
                c.drawString(40,y,line); y-=15
                if y<60: c.showPage(); y=h-40
        c.showPage(); c.save(); buf.seek(0)
        st.download_button("Download Proposal PDF", buf, "proposal.pdf","application/pdf")

# ── Footer ────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
