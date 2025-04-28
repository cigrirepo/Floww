# app.py
# Floww – AI-powered Deal Workflow & Proposal Generator
# ====================================================
#  • Real-company enrichment (ticker / Clearbit)
#  • Two-pane tabs (Workflow | Proposal)
#  • Advanced Mermaid diagrams with theming + JSON editor
#  • Competitor benchmarks, CRM playbook, PPTX export
#  • Spreadsheet-style pricing grid, presets, totals
#  • AI-generated proposal → PDF export
#  • Robust handling of pricing formats in AI output

import io, os, re, json
from datetime import date
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from pydantic import BaseModel, ValidationError
from openai import OpenAI
import yfinance as yf
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pptx import Presentation

# ── Config ────────────────────────────────────────────
st.set_page_config(page_title="Floww Advanced", layout="wide")
st.title("Floww Advanced")
st.caption("AI-driven workflows, diagrams & proposals tailored to real companies")

# ── API Clients ───────────────────────────────────────
api_key      = os.getenv("OPENAI_API_KEY")
clearbit_key = os.getenv("CLEARBIT_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY"); st.stop()
client = OpenAI(api_key=api_key)

# ── Data Models ───────────────────────────────────────
class StageModel(BaseModel):
    stage: str
    tip:   str

class WorkflowModel(BaseModel):
    workflow: List[StageModel]

class ProposalModel(BaseModel):
    title: str
    executive_summary: str
    background: str
    solution_overview: str
    deliverables: List[str]
    # allow either list or dict from AI
    pricing: Any
    next_steps: str

# ── Sidebar – Company info & presets ──────────────────
st.sidebar.header("Company Info")
company   = st.sidebar.text_input("Company name", "Acme Corp")
website   = st.sidebar.text_input("Website URL (optional)")
ticker    = st.sidebar.text_input("Stock ticker (optional)")
industry  = st.sidebar.selectbox("Industry", ["Fintech","SaaS","Retail","Healthcare","Other"])
persona   = st.sidebar.selectbox("Persona", ["Enterprise AE","SMB SDR","Partner Manager"])

# ... [unchanged workflow tab code] ...

# -----------------------------------------------------#
#                      PROPOSAL TAB                    #
# -----------------------------------------------------#
with tab_prop:
    st.subheader("Generate Proposal")

    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Proposal for (client)", key="client")
    with col2:
        prop_date = st.date_input("Date", date.today())

    deliverables_txt = st.text_area(
        "Key deliverables (one per line)",
        placeholder="Integration setup\n24/7 support\nTraining sessions",
        height=100,
    )

    st.markdown("#### Pricing Table")
    if "price_table" not in st.session_state:
        st.session_state["price_table"] = pd.DataFrame(
            [{"Item":"Integration","Qty":1,"Unit":"Lot","Unit Price":10000}]
        )

    # Preset buttons...
    # [Starter, Growth, Enterprise as before]

    price_df = st.data_editor(
        st.session_state["price_table"],
        num_rows="dynamic",
        use_container_width=True,
        key="price_editor"
    )
    price_df["Subtotal"] = price_df["Qty"] * price_df["Unit Price"]
    total = price_df["Subtotal"].sum()
    st.metric("Grand Total", f"${total:,.0f}")

    if st.button("Generate Proposal", type="primary"):
        # ---- clean pricing to native Python types ----
        price_clean = price_df[["Item","Qty","Unit","Unit Price"]].astype({
            "Qty": int,
            "Unit Price": float
        })
        records = price_clean.to_dict(orient="records")

        # ---- assemble plain-text prompt ----
        lines = [
            f"Client: {client_name}",
            f"Company: {company}",
            f"Date: {prop_date}",
            "",
            "Deliverables:"
        ] + [f"- {d}" for d in deliverables_txt.splitlines()] + [
            "",
            "Pricing:"
        ]
        for r in records:
            lines.append(f"- {r['Item']}, Qty: {r['Qty']}, Unit: {r['Unit']}, Price: ${r['Unit Price']:,.0f}")
        lines.append(f"\nTotal: ${total:,.0f}")

        sys_p = (
            "You are an expert sales engineer. "
            "Return ONLY valid JSON with keys: "
            "title, executive_summary, background, solution_overview, "
            "deliverables (list of strings), "
            "pricing (list of objects with keys item, qty, unit, price), "
            "next_steps."
        )
        user_p = "\n".join(lines)

        with st.spinner("Crafting proposal with Floww AI …"):
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":sys_p},
                    {"role":"user","content":user_p}
                ],
                temperature=0.2,
                max_tokens=750,
            )
        prop_raw = resp.choices[0].message.content

        # ---- parse & normalize pricing field ----
        try:
            proposal = ProposalModel.parse_raw(prop_raw)
        except ValidationError as e:
            st.error("AI returned invalid JSON"); st.code(prop_raw, language="json"); st.error(str(e)); st.stop()

        # If AI returned pricing as dict, convert to list
        if isinstance(proposal.pricing, dict):
            normalized = []
            for item, details in proposal.pricing.items():
                if isinstance(details, dict):
                    normalized.append({
                        "item": item,
                        "qty":   details.get("qty") or details.get("Qty") or 1,
                        "unit":  details.get("unit") or details.get("Unit") or "",
                        "price": details.get("price") or details.get("Unit Price") or 0.0
                    })
            proposal.pricing = normalized

        # ---- render proposal ----
        st.success("Proposal generated ✔︎")
        st.markdown(f"## {proposal.title}")
        st.markdown(f"### Executive Summary\n{proposal.executive_summary}")
        st.markdown(f"### Background\n{proposal.background}")
        st.markdown(f"### Solution Overview\n{proposal.solution_overview}")
        st.markdown("### Deliverables\n" + "\n".join(f"- {d}" for d in proposal.deliverables))
        st.markdown("### Pricing")
        display_df = pd.DataFrame(proposal.pricing)
        st.table(display_df)
        st.markdown(f"### Next Steps\n{proposal.next_steps}")

        # ---- PDF export (unchanged) ----
        buf = io.BytesIO()
        c   = canvas.Canvas(buf, pagesize=letter)
        w, h = letter
        y = h - 40
        def add_text(text, y_pos, indent=40, leading=14):
            for line in text.split("\n"):
                c.drawString(indent, y_pos, line)
                y_pos -= leading
                if y_pos < 60:
                    c.showPage()
                    y_pos = h - 40
            return y_pos

        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, proposal.title)
        y -= 25
        c.setFont("Helvetica", 12)

        for sec in ["executive_summary","background","solution_overview","next_steps"]:
            c.setFont("Helvetica-Bold", 12)
            y = add_text(sec.replace("_"," ").title()+":", y, 40)
            y -= 5
            c.setFont("Helvetica", 12)
            y = add_text(getattr(proposal,sec), y, 50)
            y -= 10

        c.setFont("Helvetica-Bold", 12)
        y = add_text("Pricing:", y, 40)
        y -= 5
        for row in display_df.itertuples(index=False):
            line = f"{row.item} ×{row.qty} {row.unit} … ${row.price:,.0f}"
            y = add_text(line, y, 50)
        add_text(f"Grand Total: ${total:,.0f}", y, 50)

        c.save(); buf.seek(0)
        st.download_button("Download Proposal PDF", buf, "proposal.pdf", "application/pdf")

# ── Footer ───────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
