# app.py
# Floww – AI-powered Deal Workflow Generator (v2 with advanced features)
# Includes: CSV upload playbook, competitor templates, PPTX export, persona-specific tips
# Robust JSON extraction via regex to prevent parse errors

import io
import os
import re
import json
from typing import List, Dict

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from graphviz import Digraph
from pptx import Presentation

# ── CONFIG ─────────────────────────────────────────────
st.set_page_config(page_title="Floww Advanced", layout="wide")
st.title("Floww Advanced")
st.caption("Deal workflows + personalized playbooks, competitor benchmarks, PPTX export & personas")

# ── CLIENT & AUTH ──────────────────────────────────────
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

# ── Sidebar / Inputs ───────────────────────────────────
st.sidebar.header("Input options")
company     = st.sidebar.text_input("Company name", "Acme Corp")
industry    = st.sidebar.selectbox("Industry", ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
persona     = st.sidebar.selectbox("Persona", ["Enterprise AE", "SMB SDR", "Partner Manager"])
crm_file    = st.sidebar.file_uploader("Upload CRM CSV (lead,stage,probability)", type="csv")
competitor  = st.sidebar.selectbox("Benchmark vs.", ["None", "Visa", "Stripe", "Amex"])
pptx_export = st.sidebar.checkbox("Enable PPTX Export", True)

# ── Generate Advanced Workflow ─────────────────────────
if st.sidebar.button("Generate Advanced Workflow"):
    # 1️⃣ Generate base workflow via AI with strict JSON prompt
    system_msg = (
        "You are an enterprise sales consultant. "
        "Respond with ONLY valid JSON—no markdown, no explanation. "
        "Use this schema: {\"workflow\":[{\"stage\":\"\",\"tip\":\"\"}]}"
    )
    user_msg = (
        f"Persona: {persona}. Company: {company}. Industry: {industry}. "
        "Return a deal-closing workflow in the JSON format specified
