# Floww – AI-powered Deal Workflow Generator
# =========================================
# Requirements:
#   pip install -r requirements.txt
# Environment:
#   set OPENAI_API_KEY as an environment variable
#
# Local test:
#   export OPENAI_API_KEY="sk-…"   # mac / linux
#   streamlit run app.py
#

import io
import os
import pandas as pd
import streamlit as st
import openai
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# ── Streamlit page config ──────────────────────────────────────────────────────
st.set_page_config(page_title="Floww", layout="wide")
st.title("Floww")
st.caption("AI-powered custom deal-workflow generator")

# ── OpenAI setup ───────────────────────────────────────────────────────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("OPENAI_API_KEY environment variable not found.")
    st.stop()

# ── Sidebar – user inputs ──────────────────────────────────────────────────────
st.sidebar.header("Deal Parameters")
industry     = st.sidebar.selectbox("Industry",     ["Fintech", "SaaS", "Retail", "Healthcare", "Other"])
client_type  = st.sidebar.selectbox("Client Type",  ["SMB", "Mid-Market", "Enterprise"])
deal_size    = st.sidebar.selectbox("Deal Size",    ["<100K", "100K-500K", "500K-1M", "1M-5M", ">5M"])

# ── Generate workflow button ───────────────────────────────────────────────────
if st.sidebar.button("Generate Deal Workflow"):
    with st.spinner("Building your custom deal workflow…"):

        # ── Construct prompt ───────────────────────────────────────────────────
        system_prompt = (
            "You are an expert business consultant specializing in enterprise-sales processes. "
            "Generate a clear, actionable, deal-closing workflow based on the inputs below. "
            "Return as a numbered list of stages, each with 1–2 concise best-practice tips."
        )
        user_prompt = f"""Industry: {industry}
Client Type: {client_type}
Deal Size: {deal_size}
"""

        # ── OpenAI call ────────────────────────────────────────────────────────
        try:
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500,
            )
            content = resp.choices[0].message.content
        except Exception as e:
            st.error(f"OpenAI API error: {e}")
            st.stop()

        # ── Parse numbered stages & tips ───────────────────────────────────────
        stages, tips = [], {}
        for line in (l.strip() for l in content.splitlines() if l.strip()):
            if line[0].isdigit():
                _, rest = line.split(".", 1)
                name, *tip_part = rest.split("-", 1)
                stage = name.strip()
                tip   = tip_part[0].strip() if tip_part else ""
                stages.append(stage)
                tips[stage] = tip

        if not stages:
            st.error("Couldn’t parse workflow. Try again.")
            st.stop()

        # ── Flowchart (Mermaid) ────────────────────────────────────────────────
        mermaid = "```mermaid\ngraph TD\n"
        for i in range(len(stages) - 1):
            mermaid += f"    S{i}[\"{stages[i]}\"] --> S{i+1}[\"{stages[i+1]}\"]\n"
        mermaid += "```"

        st.subheader("Deal Workflow Diagram")
        st.markdown(mermaid, unsafe_allow_html=True)

        # ── Best-practice tips ────────────────────────────────────────────────
        st.subheader("Best-Practice Tips")
        for s in stages:
            st.markdown(f"**{s}** — {tips[s]}")

        # ── CSV download ──────────────────────────────────────────────────────
        df  = pd.DataFrame({"Stage": stages, "Tip": [tips[s] for s in stages]})
        csv = df.to_csv(index=False).encode()
        st.download_button("Download CSV", csv, "deal_workflow.csv", "text/csv")

        # ── PDF generation (in-memory) ────────────────────────────────────────
        pdf_buffer = io.BytesIO()
        pdf_canvas = canvas.Canvas(pdf_buffer, pagesize=letter)
        w, h = letter
        pdf_canvas.setFont("Helvetica-Bold", 14)
        pdf_canvas.drawString(40, h - 40, "Floww — Deal Workflow")
        y = h - 80
        pdf_canvas.setFont("Helvetica", 12)
        for i, stage in enumerate(stages, 1):
            pdf_canvas.drawString(40, y, f"{i}. {stage}")
            y -= 18
            pdf_canvas.drawString(60, y, f"Tip: {tips[stage]}")
            y -= 28
            if y < 60:  # new page if needed
                pdf_canvas.showPage()
                y = h - 40
        pdf_canvas.save()
        pdf_buffer.seek(0)
        st.download_button("Download PDF", pdf_buffer, "deal_workflow.pdf", "application/pdf")

# ── Footer ────────────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Built by **Adam Cigri** with Streamlit & OpenAI")
