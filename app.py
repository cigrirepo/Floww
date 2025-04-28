# app.py  
# Floww – AI-powered Deal Workflow Generator (v2 with advanced features)  
# ===============================================================  
# Includes: CSV upload playbook, competitor templates, PPTX export, persona-specific tips

import io, os, json
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from graphviz import Digraph
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt

# ── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Floww", layout="wide")
st.title("Floww Advanced")
st.caption("Deal workflows + personalized playbooks, competitor benchmarks, PPTX export & personas")

# ── CLIENTS & MODELS ───────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY")
    st.stop()
client = OpenAI(api_key=api_key)

# ── Pydantic ───────────────────────────────────────────
class StageModel(BaseModel): stage: str; tip: str
class WorkflowModel(BaseModel): workflow: List[StageModel]

# ── Sidebar / Inputs ───────────────────────────────────
st.sidebar.header("Input options")
# Base workflow
company = st.sidebar.text_input("Company name", "Acme Corp")
industry = st.sidebar.selectbox("Industry", ["Fintech","SaaS","Retail","Healthcare","Other"])
persona = st.sidebar.selectbox("Persona","Enterprise AE,SMB SDR,Partner Manager".split(","))

# CSV upload for playbook
st.sidebar.subheader("Upload CRM CSV for Playbook")
crm_file = st.sidebar.file_uploader("CSV: lead,stage,probability", type="csv")

# Competitor benchmarking templates
st.sidebar.subheader("Select Competitor Template")
competitor = st.sidebar.selectbox("Benchmark vs.", ["None","Visa","Stripe","Amex"])

# PPTX export toggle
pptx_export = st.sidebar.checkbox("Enable PPTX Export", True)

# Generate
if st.sidebar.button("Generate Advanced Workflow"):
    # 1️⃣ Generate base workflow via AI
    prompt = (
        f"Persona: {persona}. Company: {company}. Industry: {industry}. "
        "Return JSON {'workflow':[{'stage':'','tip':''}, ... ]}."
    )
    resp = client.chat.completions.create(
        model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.0, max_tokens=800)
    data_raw = resp.choices[0].message.content
    try:
        wf = WorkflowModel.parse_raw(data_raw)
    except ValidationError:
        st.error("AI JSON parse error")
        st.code(data_raw)
        st.stop()
    stages = [s.stage for s in wf.workflow]
    tips = {s.stage:s.tip for s in wf.workflow}

    # 2️⃣ Render and show competitor template if selected
    if competitor != "None":
        # simplistic hardcoded benchmarks
        bench = {
            'Visa': ['Prospecting','KYC Check','Regulatory Review'],
            'Stripe': ['API Integration Pilot','Sandbox Testing'],
            'Amex': ['Regulatory Compliance','Fraud Assessment']
        }
        st.subheader(f"Benchmark Stages vs. {competitor}")
        st.write(bench.get(competitor, []))

    # 3️⃣ Upload CSV playbook: AI-enhanced tips per record
    if crm_file:
        df_crm = pd.read_csv(crm_file)
        playbook = []
        for idx,row in df_crm.iterrows():
            lp = row.to_dict()
            # simple AI call per lead (batch for real use)
            p_prompt = f"Lead data: {lp}. Suggest next-step tip."
            tip_resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":p_prompt}], temperature=0.7)
            playbook.append({**lp,'suggestion': tip_resp.choices[0].message.content})
        st.subheader("Personalized Playbook from CRM")
        st.dataframe(pd.DataFrame(playbook))

    # 4️⃣ Build PPTX if opted
    if pptx_export:
        prs = Presentation()
        # Title slide
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = f"Floww Playbook: {company}"
        # One slide per stage
        for s in stages:
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            slide.shapes.title.text = s
            body = slide.shapes.placeholders[1].text_frame
            body.text = tips[s]
        bio = io.BytesIO()
        prs.save(bio); bio.seek(0)
        st.download_button("Download PPTX Playbook", bio, "floww_playbook.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")

    # Show core workflow
    st.subheader("Workflow Stages & Tips")
    for s in stages:
        st.markdown(f"**{s}**: {tips[s]}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")

# requirements.txt updates:
# streamlit>=1.34
# openai>=1.14
# pandas>=2.2
# reportlab>=3.6
# graphviz>=0.20
# pydantic>=1.10
# matplotlib>=3.8
# python-pptx>=0.6.21
# flake8>=6.1

# CI unchanged
