# app.py  
# Floww – AI-powered Deal Workflow Generator (Quick‑Win Upgrade)  
# ===============================================================  
# Adds:  
#   1. Pydantic data models for robust JSON parsing  
#   2. Copy‑to‑clipboard / download of Mermaid code  
#   3. Simple What‑If sliders (deal amount & months‑to‑close)  
#
# Quick‑start:
#   export OPENAI_API_KEY="sk‑..."
#   pip install -r requirements.txt
#   streamlit run app.py

import io
import os
import json
from typing import List

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from graphviz import Digraph

# ─────────────────────────────────────────
# Streamlit page config
# ─────────────────────────────────────────
st.set_page_config(page_title="Floww", layout="wide")
st.title("Floww")
st.caption("AI‑powered custom deal‑workflow generator")

# ─────────────────────────────────────────
# OpenAI client setup
# ─────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OPENAI_API_KEY missing in environment / Secrets.")
    st.stop()
client = OpenAI(api_key=api_key)

# ─────────────────────────────────────────
# Pydantic models for robust parsing
# ─────────────────────────────────────────
class StageModel(BaseModel):
    stage: str
    tip:   str

class WorkflowModel(BaseModel):
    workflow: List[StageModel]

# ─────────────────────────────────────────
# Sidebar inputs
# ─────────────────────────────────────────
st.sidebar.header("Deal parameters")
company = st.sidebar.text_input("Company name (optional)")
industry = st.sidebar.selectbox("Industry", ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
client_type = st.sidebar.selectbox("Client type", ["SMB", "Mid‑Market", "Enterprise"])

deal_amount = st.sidebar.number_input("Deal amount (USD)", min_value=1000, step=5000, value=100000)
months_to_close = st.sidebar.slider("Expected months to close", 1, 24, 6)

deal_size_bucket = (
    "<100K" if deal_amount < 100_000 else
    "100K-500K" if deal_amount < 500_000 else
    "500K-1M" if deal_amount < 1_000_000 else
    "1M-5M" if deal_amount < 5_000_000 else ">5M"
)

# ─────────────────────────────────────────
# Generate workflow
# ─────────────────────────────────────────
if st.sidebar.button("Generate deal workflow"):
    with st.spinner("Generating workflow…"):
        system_msg = (
            "You are an enterprise sales consultant. "
            "Respond ONLY with valid JSON: { 'workflow': [ { 'stage':'', 'tip':'' }, … ] }"
        )
        user_msg = (
            f"Generate a deal‑closing workflow for '{company or 'a client'}' in {industry}. "
            f"Client type: {client_type}. Deal size bucket: {deal_size_bucket}."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_msg}, {"role":"user","content":user_msg}],
            temperature=0.0,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content

        # Robust parse via Pydantic
        try:
            wf_obj = WorkflowModel.parse_raw(raw)
        except ValidationError:
            st.error("Failed JSON schema validation – raw output below:")
            st.code(raw, language="json")
            st.stop()

        stages = [s.stage for s in wf_obj.workflow]
        tips   = {s.stage: s.tip for s in wf_obj.workflow}

        # ── Mermaid code & copy helpers ─────────────────────
        mermaid_code = "flowchart TD\n" + "\n".join(
            f"  S{i}[{stages[i]}] --> S{i+1}[{stages[i+1]}]" for i in range(len(stages)-1)
        )
        mermaid_block = f"```mermaid\n{mermaid_code}\n```"

        st.subheader("Mermaid Diagram (copy or download)")
        st.code(mermaid_block, language="")
        st.download_button("Download .mmd", mermaid_code.encode(), "workflow.mmd", "text/plain")

        # Simple JS copy‑to‑clipboard (Streamlit ≥1.30)
        st.button("Copy to clipboard", on_click=lambda: st.experimental_set_query_params(code=mermaid_code))

        st.markdown(mermaid_block, unsafe_allow_html=True)

        # ── Graphviz fallback ───────────────────────────────
        dot = Digraph()
        for i,s in enumerate(stages):
            dot.node(f"S{i}", s)
        for i in range(len(stages)-1):
            dot.edge(f"S{i}", f"S{i+1}")
        st.graphviz_chart(dot.source)

        # ── Best‑practice tips ──────────────────────────────
        st.subheader("Best‑Practice Tips")
        for s in stages:
            st.markdown(f"**{s}** — {tips[s]}")

        # ── What‑If: simple revenue timeline ───────────────
        st.subheader("What‑If: Revenue Timeline")
        expected_close_date = months_to_close / 12
        st.write(f"**Expected deal amount:** ${deal_amount:,.0f}")
        st.write(f"**Months to close:** {months_to_close} (≈ {expected_close_date:.1f} years)")
        st.write("(Enhance this section later with charts or NPV calculations.)")

        # ── Downloads (CSV, PDF) remain unchanged ──────────
        df = pd.DataFrame({"stage": stages, "tip": [tips[s] for s in stages]})
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "deal_workflow.csv", "text/csv")

        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=letter)
        w,h = letter
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, h-40, f"Floww Workflow for {company or 'Client'}")
        y = h-80
        pdf.setFont("Helvetica", 12)
        for i,s in enumerate(stages,1):
            pdf.drawString(40,y, f"{i}. {s}")
            y -= 18
            pdf.drawString(60,y, f"Tip: {tips[s]}")
            y -= 28
            if y < 60:
                pdf.showPage(); y = h-40
        pdf.save(); buf.seek(0)
        st.download_button("Download PDF", buf, "deal_workflow.pdf", "application/pdf")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built by **Adam Cigri** with Streamlit & OpenAI")

# ====================== requirements.txt =====================
# streamlit>=1.34
# openai>=1.14
# pandas>=2.2
# reportlab>=3.6
# graphviz>=0.20
# pydantic>=1.10
# flake8>=6.1

#  ========== .github/workflows/ci.yml (unchanged) ==========
