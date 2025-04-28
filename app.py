# app.py
# Floww – AI-powered Deal Workflow & Proposal Generator
# ====================================================
#  • Real-company enrichment (ticker / Clearbit)
#  • Two-pane tabs (Workflow | Proposal)
#  • Advanced Mermaid diagrams with theming + JSON editor
#  • Competitor benchmarks, CRM playbook, PPTX export
#  • Spreadsheet-style pricing grid, presets, totals
#  • AI-generated proposal → PDF export
#  • Big 3: ROI, Timeline Gantt, Risk & Mitigation
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
    st.error("Missing OPENAI_API_KEY")
    st.stop()
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
    pricing: Any
    next_steps: str
    npv: float
    payback_years: float
    timeline_gantt: str
    risks: List[Dict[str,str]]

# ── Sidebar – Company info & presets ──────────────────
st.sidebar.header("Company Info")
company   = st.sidebar.text_input("Company name", "Acme Corp")
website   = st.sidebar.text_input("Website URL (optional)")
ticker    = st.sidebar.text_input("Stock ticker (optional)")
industry  = st.sidebar.selectbox("Industry", ["Fintech","SaaS","Retail","Healthcare","Other"])
persona   = st.sidebar.selectbox("Persona", ["Enterprise AE","SMB SDR","Partner Manager"])

# Company enrichment
description = {
    "Fintech":"a regulated financial services provider",
    "SaaS":"a fast-growing SaaS company",
    "Retail":"a global retail chain",
    "Healthcare":"a healthcare technology provider",
    "Other":"a leading enterprise"
}[industry]
market_cap = None
if ticker:
    try:
        info = yf.Ticker(ticker).info
        description = info.get("longBusinessSummary", description)
        cap = info.get("marketCap")
        market_cap = f"${cap:,.0f}" if cap else None
    except: pass
elif website and clearbit_key:
    try:
        r = requests.get(
            f"https://company.clearbit.com/v1/domains/find?domain={website}",
            headers={"Authorization": f"Bearer {clearbit_key}"}, timeout=4
        )
        description = r.json().get("description", description)
    except: pass

st.sidebar.header("Advanced Options")
crm_file   = st.sidebar.file_uploader("CRM CSV (lead,stage,probability)", type="csv")
competitor = st.sidebar.selectbox("Competitor Benchmark", ["None","Visa","Stripe","Amex"])
pptx_ok    = st.sidebar.checkbox("Enable PPTX Export", True)

# ── Tabs ──────────────────────────────────────────────
tab_wf, tab_prop = st.tabs(["Workflow","Proposal"])

# -----------------------------------------------------#
#                   WORKFLOW TAB                       #
# -----------------------------------------------------#
with tab_wf:
    if st.button("Generate Workflow"):
        system = (
            "You are an enterprise sales consultant. "
            "Return ONLY valid JSON: {\"workflow\":[{\"stage\":\"\",\"tip\":\"\"}]}"
        )
        prompt = (
            f"Build a deal-closing workflow for a {persona} at {company}. "
            f"Desc: {description[:200]}. Industry: {industry}. Market cap: {market_cap or 'N/A'}."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},
                      {"role":"user","content":prompt}],
            temperature=0.0, max_tokens=600
        )
        raw = resp.choices[0].message.content
        m = re.search(r"{.*}", raw, re.S)
        if not m:
            st.error("AI did not return JSON"); st.code(raw); st.stop()
        js = m.group(0)
        try:
            wf = WorkflowModel.parse_raw(js)
        except ValidationError as e:
            st.error("Invalid JSON"); st.code(js); st.error(str(e)); st.stop()
        st.session_state["wf_json"]  = js
        st.session_state["stages"]   = [s.stage for s in wf.workflow]
        st.session_state["tips"]     = {s.stage:s.tip for s in wf.workflow}

    if "wf_json" in st.session_state:
        st.subheader("Edit Workflow JSON")
        edit = st.text_area("JSON", st.session_state["wf_json"], height=200)
        if st.button("Re-Render"):
            try:
                wf = WorkflowModel.parse_raw(edit)
                st.session_state["wf_json"] = edit
                st.session_state["stages"]  = [s.stage for s in wf.workflow]
                st.session_state["tips"]    = {s.stage:s.tip for s in wf.workflow}
            except: st.error("Invalid JSON")

    if "stages" in st.session_state:
        theme = "%%{init:{'themeVariables':{'primaryColor':'#00ADEF','lineColor':'#888'}}}%%\n"
        sys_d = "You are a diagram expert. Return Mermaid flowchart only."
        usr_d = f"Stages: {st.session_state['stages']}. Company: {company}."
        mr = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys_d},{"role":"user","content":usr_d}],
            temperature=0.0, max_tokens=200
        ).choices[0].message.content
        mcode = re.sub(r"^```(?:mermaid)?|```$","",mr,flags=re.M).strip()
        full = theme + mcode
        st.markdown("##### Mermaid Diagram")
        st.code(full)
        st.markdown(f"```mermaid\n{full}\n```", unsafe_allow_html=True)

        if competitor!="None":
            bench = {
                "Visa":["Prospecting","KYC Check","Reg Review"],
                "Stripe":["API Pilot","Sandbox Testing"],
                "Amex":["Reg Compliance","Fraud Assessment"]
            }
            st.write("**Benchmark vs.**", competitor, bench.get(competitor, []))

        if crm_file:
            df = pd.read_csv(crm_file)
            play = []
            for _,r in df.iterrows():
                ans = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role":"user","content":f\"Lead: {r.to_dict()}. Next step?\"}],
                    temperature=0.7, max_tokens=100
                ).choices[0].message.content
                play.append({**r.to_dict(),"suggestion":ans})
            st.dataframe(pd.DataFrame(play))

        if pptx_ok:
            prs = Presentation()
            slide0 = prs.slides.add_slide(prs.slide_layouts[0])
            slide0.shapes.title.text = f"Floww Playbook: {company}"
            for s in st.session_state["stages"]:
                sld = prs.slides.add_slide(prs.slide_layouts[1])
                sld.shapes.title.text = s
                sld.placeholders[1].text = st.session_state["tips"][s]
            bio = io.BytesIO(); prs.save(bio); bio.seek(0)
            st.download_button("Download PPTX", bio, "playbook.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation")

# -----------------------------------------------------#
#                   PROPOSAL TAB                       #
# -----------------------------------------------------#
with tab_prop:
    st.subheader("Generate Proposal")

    # Client & timeline inputs
    c1,c2,c3 = st.columns([3,2,2])
    with c1:
        client_name = st.text_input("Client name", key="client")
    with c2:
        prop_date   = st.date_input("Date", date.today())
    with c3:
        months      = st.slider("Timeline (months)", 1, 18, 6)

    # ROI inputs
    benefit     = st.number_input("Annual benefit ($)", 10000, step=1000)
    discount    = st.slider("Discount rate %", 0.0, 30.0, 10.0, step=0.1)
    yrs         = st.slider("Benefit years", 1, 10, 3)
    npv = sum(benefit/(1+discount/100)**y for y in range(1,yrs+1)) - total if "total" in locals() else 0.0
    payback = (total/benefit) if "total" in locals() and benefit>0 else 0.0
    st.metric("NPV", f"${npv:,.0f}")
    st.metric("Payback (yrs)", f"{payback:.1f}")

    # Risks input & AI table
    risk_txt = st.text_area("Top 3 risks (one per line)", height=80)
    if risk_txt.strip():
        with st.spinner("Analyzing risks…"):
            risk_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":"Return a markdown table with columns Risk | Mitigation."},
                    {"role":"user","content":f"Risks:\n{risk_txt}"}
                ],
                temperature=0.0, max_tokens=200
            ).choices[0].message.content
        st.markdown("#### Risk & Mitigation")
        st.markdown(risk_resp, unsafe_allow_html=True)

    # Deliverables & pricing grid
    deliverables_txt = st.text_area("Deliverables\n(one per line)", height=100)
    st.markdown("#### Pricing Table")
    if "price_table" not in st.session_state:
        st.session_state["price_table"] = pd.DataFrame([{"Item":"Integration","Qty":1,"Unit":"Lot","Unit Price":10000}])
    dfp = st.data_editor(st.session_state["price_table"], num_rows="dynamic", use_container_width=True, key="price")
    dfp["Subtotal"] = dfp["Qty"]*dfp["Unit Price"]
    total = dfp["Subtotal"].sum()
    st.metric("Grand Total", f"${total:,.0f}")

    # Gantt chart
    gantt = (
        f"gantt\n"
        f"  title Implementation Timeline\n"
        f"  dateFormat  YYYY-MM-DD\n"
        f"  section Rollout\n"
        f"  Kickoff      :a1, 2025-05-01, 15d\n"
        f"  Integration  :after a1, {months*30//2}d\n"
        f"  Training     :after a1, 15d\n"
        f"  Go-Live      :milestone, after a1, 1d\n"
    )
    st.markdown("#### Implementation Timeline")
    st.markdown(f"```mermaid\n{gantt}\n```", unsafe_allow_html=True)

    # Generate Proposal
    if st.button("Generate Proposal", type="primary"):
        # clean pricing for JSON
        clean = dfp[["Item","Qty","Unit","Unit Price"]].astype({"Qty":int,"Unit Price":float})
        recs = clean.to_dict(orient="records")

        # build prompt
        lines = [
            f"Client: {client_name}",
            f"Company: {company}",
            f"Date: {prop_date}",
            f"Timeline: {months} months",
            f"NPV: {npv:.0f}, Payback: {payback:.1f} yrs",
            "",
            "Deliverables:"
        ] + [f"- {d}" for d in deliverables_txt.splitlines()] + ["", "Pricing:"]
        for r in recs:
            lines.append(f"- {r['Item']} x{r['Qty']} {r['Unit']}: ${r['Unit Price']:,.0f}")
        lines += ["", "Timeline Gantt:", gantt, "", "Risks:", risk_txt]

        sys_p = (
            "You are an expert sales engineer. "
            "Return ONLY valid JSON with keys: "
            "title, executive_summary, background, solution_overview, "
            "deliverables, pricing, next_steps, npv, payback_years, timeline_gantt, risks."
        )
        user_p = "\n".join(lines)

        with st.spinner("Crafting proposal…"):
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":sys_p},{"role":"user","content":user_p}],
                temperature=0.2, max_tokens=900
            )
        raw = resp.choices[0].message.content
        try:
            proposal = ProposalModel.parse_raw(raw)
        except ValidationError as e:
            st.error("Invalid JSON from AI"); st.code(raw); st.error(str(e)); st.stop()

        # normalize pricing if dict
        if isinstance(proposal.pricing, dict):
            norm=[]
            for k,v in proposal.pricing.items():
                if isinstance(v,dict):
                    norm.append({
                        "item":k,
                        "qty":v.get("qty") or v.get("Qty") or 1,
                        "unit":v.get("unit") or v.get("Unit") or "",
                        "price":v.get("price") or v.get("Unit Price") or 0.0
                    })
            proposal.pricing=norm

        # render
        st.success("Proposal generated ✔︎")
        st.markdown(f"# {proposal.title}")
        st.markdown(f"**Executive Summary**\n{proposal.executive_summary}")
        st.markdown(f"**Background**\n{proposal.background}")
        st.markdown(f"**Solution Overview**\n{proposal.solution_overview}")
        st.markdown("**Deliverables**\n" + "\n".join(f"- {d}" for d in proposal.deliverables))
        st.markdown("**Pricing**")
        st.table(pd.DataFrame(proposal.pricing))
        st.markdown("**Implementation Timeline**")
        st.markdown(f"```mermaid\n{proposal.timeline_gantt}\n```", unsafe_allow_html=True)
        st.markdown("**Risks & Mitigation**")
        st.table(pd.DataFrame(proposal.risks))
        st.markdown("**Next Steps**\n" + proposal.next_steps)
        st.metric("NPV", f"${proposal.npv:,.0f}")
        st.metric("Payback (yrs)", f"{proposal.payback_years:.1f}")

        # PDF export
        buf=io.BytesIO(); c=canvas.Canvas(buf,pagesize=letter); w,h=letter; y=h-40
        def add_text(txt,y_pos,indent=40,leading=14):
            for l in txt.split("\n"):
                c.drawString(indent,y_pos,l); y_pos-=leading
                if y_pos<60: c.showPage(); y_pos=h-40
            return y_pos

        c.setFont("Helvetica-Bold",16); c.drawString(40,y,proposal.title); y-=25
        c.setFont("Helvetica",12)
        for sec in ["executive_summary","background","solution_overview","next_steps"]:
            c.setFont("Helvetica-Bold",12); y=add_text(sec.replace("_"," ").title()+":",y)
            y=add_text(getattr(proposal,sec),y,50); y-=10
        c.setFont("Helvetica-Bold",12); y=add_text("Pricing:",y)
        for row in pd.DataFrame(proposal.pricing).itertuples(index=False):
            y=add_text(f"{row.item} x{row.qty} {row.unit} – ${row.price:,.0f}",y,50)
        y=add_text("Implementation Timeline:",y)
        y=add_text(proposal.timeline_gantt,y,50)
        st.download_button("Download Proposal PDF", buf, "proposal.pdf","application/pdf")

# ── Footer ───────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Adam Cigri & OpenAI")
