# Floww – AI-powered Deal Workflow Generator
# ==================================================
# Repo structure expected
# ├── app.py                  ← this file
# ├── requirements.txt        ← see bottom
# └── .github/
#     └── workflows/
#         └── ci.yml
#
# Quick-start
#   export OPENAI_API_KEY="sk-…"
#   pip install -r requirements.txt
#   streamlit run app.py
#
import io
import os
from typing import List, Tuple

import pandas as pd
import streamlit as st
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from graphviz import Digraph

# ────────────────────────────────────────────────────
# Streamlit config
# ────────────────────────────────────────────────────
st.set_page_config(page_title="Floww", layout="wide")
st.title("Floww")
st.caption("AI-powered custom deal-workflow generator")

# ────────────────────────────────────────────────────
# OpenAI client
# ────────────────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Environment variable OPENAI_API_KEY is missing.")
    st.stop()
client = OpenAI(api_key=api_key)

# ────────────────────────────────────────────────────
# Sidebar – parameters
# ────────────────────────────────────────────────────
st.sidebar.header("Deal parameters")
company     = st.sidebar.text_input("Company name (optional)", "")
industry    = st.sidebar.selectbox("Industry", ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
client_type = st.sidebar.selectbox("Client type", ["SMB", "Mid-Market", "Enterprise"])
deal_size   = st.sidebar.selectbox("Deal size", ["<100K", "100K-500K", "500K-1M", "1M-5M", ">5M"])

# ────────────────────────────────────────────────────
# Parse stages from AI output
# ────────────────────────────────────────────────────
def parse_stages(text: str) -> Tuple[List[str], dict]:
    stages: List[str] = []
    tips: dict[str, str] = {}
    for line in (l.strip() for l in text.splitlines() if l.strip()):
        if line[0].isdigit():
            _, rest = line.split(".", 1)
            name, *tip_part = rest.split("-", 1)
            stage = name.strip()
            tip = tip_part[0].strip() if tip_part else ""
            stages.append(stage)
            tips[stage] = tip
    return stages, tips

# ────────────────────────────────────────────────────
# Generate workflow
# ────────────────────────────────────────────────────
if st.sidebar.button("Generate deal workflow"):
    with st.spinner("Generating workflow…"):
        # Construct prompt
        prompt = (
            "You are an expert business consultant for enterprise-sales processes. "
            f"Generate a detailed deal-closing workflow for {company or 'the client'} in {industry}. "
            f"Client Type: {client_type}, Deal Size: {deal_size}. "
            "Return as a numbered list of stages. For each stage, add 1–2 best-practice tips."
        )
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600,
            )
            raw = resp.choices[0].message.content
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
            st.stop()

        # Parse AI output
        stages, tips = parse_stages(raw)
        if not stages:
            st.error("Could not parse workflow. Here's raw output:")
            st.text(raw)
            st.stop()

        # ── Visual workflow with Graphviz ──
        dot = Digraph("Workflow", format="png")
        for i, stage in enumerate(stages):
            dot.node(f"S{i}", stage)
        for i in range(len(stages)-1):
            dot.edge(f"S{i}", f"S{i+1}")
        st.subheader("Workflow Visualization")
        st.graphviz_chart(dot.source)

        # ── Best-practice tips ──
        st.subheader("Best-Practice Tips")
        for s in stages:
            st.markdown(f"**{s}** — {tips[s]}")

        # ── Download CSV ──
        df = pd.DataFrame({"Stage": stages, "Tip": [tips[s] for s in stages]})
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "deal_workflow.csv", "text/csv")

        # ── Download PDF ──
        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=letter)
        w, h = letter
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, h-40, f"Floww Workflow for {company or 'Client'}")
        y = h-80
        pdf.setFont("Helvetica", 12)
        for i, s in enumerate(stages, 1):
            pdf.drawString(40, y, f"{i}. {s}")
            y -= 18
            pdf.drawString(60, y, f"Tip: {tips[s]}")
            y -= 28
            if y < 60:
                pdf.showPage()
                y = h-40
        pdf.save()
        buf.seek(0)
        st.download_button("Download PDF", buf, "deal_workflow.pdf", "application/pdf")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built by **Adam Cigri** with Streamlit & OpenAI")
