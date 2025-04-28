import io, os, json
from typing import List, Dict
import numpy as np
import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from graphviz import Digraph
import matplotlib.pyplot as plt

# ── UI config ─────────────────────────────────────────
st.set_page_config(page_title="Floww", layout="wide")
st.title("Floww")
st.caption("AI-powered custom deal-workflow generator")

# ── OpenAI client ────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OPENAI_API_KEY missing.")
    st.stop()
client = OpenAI(api_key=api_key)

# ── Pydantic models ──────────────────────────────────
class StageModel(BaseModel):
    stage: str
    tip:   str
class WorkflowModel(BaseModel):
    workflow: List[StageModel]

# ── Sidebar inputs ───────────────────────────────────
st.sidebar.header("Deal parameters")
company      = st.sidebar.text_input("Company name (optional)")
industry     = st.sidebar.selectbox("Industry",    ["Fintech","SaaS","Retail","Healthcare","Other"])
client_type  = st.sidebar.selectbox("Client type", ["SMB","Mid-Market","Enterprise"])
deal_amount  = st.sidebar.number_input("Deal amount (USD)", 1_000, value=200_000, step=10_000)
months_close = st.sidebar.slider("Months to close", 1, 24, 11)
discount     = st.sidebar.slider("Discount rate (annual %)", 0.0, 20.0, 8.0)

# Bucket for prompt
bucket = ("<100K" if deal_amount<100_000 else
          "100K-500K" if deal_amount<500_000 else
          "500K-1M"   if deal_amount<1_000_000 else
          "1M-5M"     if deal_amount<5_000_000 else ">5M")

# ── Generate button ──────────────────────────────────
if st.sidebar.button("Generate deal workflow"):
    with st.spinner("Calling Floww AI…"):
        system_msg = (
            "You are an enterprise sales consultant. "
            "Output ONLY valid JSON: {\"workflow\":[{\"stage\":\"\",\"tip\":\"\"},…]}"
        )
        user_msg = (f"Generate a deal-closing workflow for '{company or 'a client'}' in {industry}. "
                    f"Client type={client_type}. Deal size bucket={bucket}.")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system_msg},
                      {"role":"user","content":user_msg}],
            temperature=0.0,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content

    # ── Parse JSON safely ────────────────────────────
    try:
        wf = WorkflowModel.parse_raw(raw)
    except ValidationError:
        st.error("JSON schema validation failed. Raw output:")
        st.code(raw, language="json")
        st.stop()

    stages = [s.stage for s in wf.workflow]
    tips   = {s.stage: s.tip for s in wf.workflow}

    # ── Mermaid code & render ────────────────────────
    mermaid_code = "flowchart TD\n" + "\n".join(
        f"  S{i}[{stages[i]}] --> S{i+1}[{stages[i+1]}]"
        for i in range(len(stages)-1)
    )
    st.subheader("Mermaid diagram")
    st.code(f"```mermaid\n{mermaid_code}\n```")
    st.download_button("Download .mmd", mermaid_code.encode(),
                       "workflow.mmd", "text/plain")
    st.markdown(f"```mermaid\n{mermaid_code}\n```", unsafe_allow_html=True)

    # ── Graphviz fallback ────────────────────────────
    dot = Digraph()
    for i,s in enumerate(stages): dot.node(f"S{i}", s)
    for i in range(len(stages)-1): dot.edge(f"S{i}", f"S{i+1}")
    st.graphviz_chart(dot.source)

    # ── Tips list ────────────────────────────────────
    st.subheader("Best-Practice Tips")
    for s in stages:
        st.markdown(f"**{s}** — {tips[s]}")

    # ── What-If: revenue timeline & NPV ──────────────
    st.subheader("What-If: Revenue timeline & NPV")
    years = months_close/12
    discount_factor = (1 + discount/100) ** (-years)
    npv = deal_amount * discount_factor
    st.write(f"**Expected deal amount:** ${deal_amount:,.0f}")
    st.write(f"**Months to close:** {months_close}  (~{years:.1f} years)")
    st.write(f"**Discount rate:** {discount:.1f}%  →  **NPV:** "
             f"${npv:,.0f}")

    # simple timeline cash-flow chart
    t = np.linspace(0, years, 100)
    cash = np.where(t>=years, deal_amount, 0)
    fig, ax = plt.subplots()
    ax.plot(t, cash)
    ax.set_xlabel("Years")
    ax.set_ylabel("Cash inflow ($)")
    ax.set_title("Projected cash receipt")
    st.pyplot(fig)

    # ── Downloads ───────────────────────────────────
    df = pd.DataFrame({"stage": stages,
                       "tip":   [tips[s] for s in stages]})
    st.download_button("Download CSV", df.to_csv(index=False).encode(),
                       "deal_workflow.csv", "text/csv")

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=letter)
    w,h = letter; pdf.setFont("Helvetica-Bold",14)
    pdf.drawString(40, h-40, f"Floww workflow for {company or 'Client'}")
    y = h-80; pdf.setFont("Helvetica",12)
    for i,s in enumerate(stages,1):
        pdf.drawString(40,y, f"{i}. {s}"); y-=18
        pdf.drawString(60,y, f"Tip: {tips[s]}"); y-=28
        if y<60: pdf.showPage(); y = h-40
    pdf.save(); buf.seek(0)
    st.download_button("Download PDF", buf,
                       "deal_workflow.pdf", "application/pdf")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built by **Adam Cigri** with Streamlit & OpenAI")
