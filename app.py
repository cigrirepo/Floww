# app.py
# Floww – AI-powered Deal Workflow Generator
# ==================================================
# Quick-start:
#   export OPENAI_API_KEY="sk-..."
#   pip install -r requirements.txt
#   streamlit run app.py

import io
import os
import json
from typing import List, Dict

import pandas as pd
import streamlit as st
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from graphviz import Digraph

# ─────────────────────────────────────────
# Streamlit page config
# ─────────────────────────────────────────
st.set_page_config(page_title="Floww", layout="wide")
st.title("Floww")
st.caption("AI-powered custom deal-workflow generator")

# ─────────────────────────────────────────
# OpenAI client setup
# ─────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Environment variable OPENAI_API_KEY is missing.")
    st.stop()
client = OpenAI(api_key=api_key)

# ─────────────────────────────────────────
# Sidebar inputs
# ─────────────────────────────────────────
st.sidebar.header("Deal parameters")
company     = st.sidebar.text_input("Company name (optional)", "")
industry    = st.sidebar.selectbox("Industry",    ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
client_type = st.sidebar.selectbox("Client type", ["SMB", "Mid-Market", "Enterprise"])
deal_size   = st.sidebar.selectbox("Deal size",   ["<100K", "100K-500K", "500K-1M", "1M-5M", ">5M"])

# ─────────────────────────────────────────
# Parse AI JSON to stages/tips
# ─────────────────────────────────────────
def parse_workflow(data: Dict) -> (List[str], Dict[str, str]):
    workflow = data.get("workflow", [])
    stages = [step.get("stage", "") for step in workflow]
    tips = {step.get("stage", ""): step.get("tip", "") for step in workflow}
    return stages, tips

# ─────────────────────────────────────────
# Generate workflow
# ─────────────────────────────────────────
if st.sidebar.button("Generate deal workflow"):
    with st.spinner("Generating workflow…"):
        # Construct system + user messages enforcing strict JSON output
        system_msg = (
            "You are an enterprise sales consultant. "
            "Output must be ONLY valid JSON with a single key 'workflow'. "
            "'workflow' is a list of objects, each with 'stage' and 'tip' fields."
        )
        user_msg = (
            f"Generate a deal-closing workflow for '{company or 'the client'}' in {industry}. "
            f"Client type: {client_type}, Deal size: {deal_size}."
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.0,
                max_tokens=800,
            )
            raw = resp.choices[0].message.content
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
            st.stop()

        # Debug: show raw if JSON parse fails
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            st.error("Failed to parse JSON from AI. Raw output below:")
            st.code(raw, language='json')
            st.stop()

        stages, tips = parse_workflow(data)
        if not stages:
            st.error("No workflow items found in JSON.")
            st.stop()

        # ── Visual workflow with Graphviz ──
        dot = Digraph("Workflow", format="png")
        for i, s in enumerate(stages):
            label = f"{s} ({company})" if company and i == 0 else s
            dot.node(f"S{i}", label)
        for i in range(len(stages) - 1):
            dot.edge(f"S{i}", f"S{i+1}")
        st.subheader("Workflow Visualization")
        st.graphviz_chart(dot.source)

        # ── Best-practice tips ──
        st.subheader("Best-Practice Tips")
        for s in stages:
            st.markdown(f"**{s}** — {tips.get(s, '')}")

        # ── Download CSV ──
        df = pd.DataFrame({'stage': stages, 'tip': [tips[s] for s in stages]})
        st.download_button("Download CSV", df.to_csv(index=False).encode(), "deal_workflow.csv", "text/csv")

        # ── Download PDF ──
        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=letter)
        w, h = letter
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, h - 40, f"Floww Workflow for {company or 'Client'}")
        y = h - 80
        pdf.setFont("Helvetica", 12)
        for i, s in enumerate(stages, 1):
            pdf.drawString(40, y, f"{i}. {s}")
            y -= 18
            pdf.drawString(60, y, f"Tip: {tips.get(s, '')}")
            y -= 28
            if y < 60:
                pdf.showPage()
                y = h - 40
        pdf.save()
        buf.seek(0)
        st.download_button("Download PDF", buf, "deal_workflow.pdf", "application/pdf")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built by **Adam Cigri** with Streamlit & OpenAI")
