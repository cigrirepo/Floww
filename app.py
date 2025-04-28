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
# Generate workflow
# ─────────────────────────────────────────
if st.sidebar.button("Generate deal workflow"):
    with st.spinner("Generating workflow…"):
        # Construct a JSON-based prompt for robust parsing
        prompt = (
            "You are an enterprise sales consultant. "
            f"Generate a detailed deal-closing workflow for '{company or 'the client'}' in {industry}. "
            f"Client type is {client_type}, deal size is {deal_size}. "
            "Return the response as valid JSON with a key 'workflow', which is a list of objects. "
            "Each object must have 'stage' and 'tip' fields. Example output format: "
            "{ 'workflow': [ { 'stage': 'Prospecting', 'tip': 'Use ... ' }, ... ] }"
        )
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.7,
                max_tokens=800,
            )
            raw = resp.choices[0].message.content
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
            st.stop()

        # Parse JSON response
        try:
            data = json.loads(raw)
            workflow: List[Dict[str, str]] = data.get('workflow', [])
        except json.JSONDecodeError:
            st.error("Failed to parse JSON from AI. Raw output below:")
            st.code(raw, language='json')
            st.stop()

        if not workflow:
            st.error("No workflow items found in JSON.")
            st.stop()

        stages = [item['stage'] for item in workflow]
        tips = {item['stage']: item.get('tip', '') for item in workflow}

        # ── Visual workflow with Graphviz ──
        dot = Digraph("Workflow", format="png")
        for i, s in enumerate(stages):
            label = s
            if company:
                label = f"{s}\n({company})" if i == 0 else s
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
        st.download_button(
            "Download CSV", df.to_csv(index=False).encode(), "deal_workflow.csv", "text/csv"
        )

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
            pdf.drawString(60, y, f"Tip: {tips.get(s, '')}")
            y -= 28
            if y < 60:
                pdf.showPage()
                y = h-40
        pdf.save()
        buf.seek(0)
        st.download_button(
            "Download PDF", buf, "deal_workflow.pdf", "application/pdf"
        )

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built by **Adam Cigri** with Streamlit & OpenAI")
