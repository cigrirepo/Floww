# app.py
# Floww – AI-powered Deal Workflow & Proposal Generator
# ====================================================
# • Real-company enrichment (ticker / Clearbit)
# • Two-pane tabs (Workflow | Proposal)
# • Advanced Mermaid diagrams with theming + JSON editor
# • Competitor benchmarks, CRM playbook, PPTX export
# • Spreadsheet-style pricing grid, presets, totals
# • AI-generated proposal → PDF export

import io, os, re, json
from datetime import date
from typing import List, Dict

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
clearbit_key = os.getenv("CLEARBIT_KEY")           # optional
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
    pricing: List[Dict]
    next_steps: str

# ── Sidebar – Company info & presets ──────────────────
st.sidebar.header("Company Info")
company     = st.sidebar.text_input("Company name", "Acme Corp")
website     = st.sidebar.text_input("Website URL (optional)")
ticker      = st.sidebar.text_input("Stock ticker (optional)")
industry    = st.sidebar.selectbox("Industry", ["Fintech","SaaS","Retail","Healthcare","Other"])
persona     = st.sidebar.selectbox("Persona", ["Enterprise AE","SMB SDR","Partner Manager"])

# Fetch description / market cap when possible
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
            headers={"Authorization": f"Bearer {clearbit_key}"}, timeout=4)
        description = r.json().get("description", description)
    except: pass

# Other sidebar bits
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
        # ---- Call AI for workflow JSON ----
        system = ("You are an enterprise sales consultant. "
                  "Return ONLY valid JSON: {'workflow':[{'stage':'','tip':''},…]}")
        prompt = (f"Build a deal-closing workflow for a {persona} at {company}. "
                  f"Company description: {description[:200]}. "
                  f"Industry: {industry}. Market cap: {market_cap or 'N/A'}.")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},
                      {"role":"user","content":prompt}],
            temperature=0.0, max_tokens=600)
        raw = resp.choices[0].message.content
        match = re.search(r"{.*}", raw, re.S)
        if not match:
            st.error("AI did not return JSON"); st.code(raw); st.stop()
        wf_json = match.group(0)
        try:
            wf = WorkflowModel.parse_raw(wf_json)
        except ValidationError as e:
            st.error("Invalid JSON"); st.code(wf_json); st.error(str(e)); st.stop()
        st.session_state["wf_json"] = wf_json
        st.session_state["stages"]  = [s.stage for s in wf.workflow]
        st.session_state["tips"]    = {s.stage:s.tip for s in wf.workflow}

    # ---- Editable JSON area ----
    if "wf_json" in st.session_state:
        st.subheader("Edit workflow JSON (live)")
        new_json = st.text_area("JSON", st.session_state["wf_json"], height=200)
        if st.button("Re-Render Diagram"):
            try:
                wf = WorkflowModel.parse_raw(new_json)
                st.session_state["wf_json"] = new_json
                st.session_state["stages"]  = [s.stage for s in wf.workflow]
                st.session_state["tips"]    = {s.stage:s.tip for s in wf.workflow}
            except: st.error("Invalid JSON")

    # ---- Mermaid diagram ----
    if "stages" in st.session_state:
        theme = "%%{init:{'themeVariables':{'primaryColor':'#00ADEF','lineColor':'#888'}}}%%\n"
        sys_d = "You are a diagram expert. Return Mermaid flowchart only."
        usr_d = f"Stages: {st.session_state['stages']}. Company: {company}."
        mcode = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sys_d},
                      {"role":"user","content":usr_d}],
            temperature=0.0, max_tokens=200).choices[0].message.content
        mcode = re.sub(r"^```(?:mermaid)?|```$","",mcode,flags=re.M).strip()
        full_code = theme + mcode
        st.markdown("##### Mermaid Diagram")
        st.code(full_code)
        st.markdown(f"```mermaid\n{full_code}\n```", unsafe_allow_html=True)

    # ---- Benchmarks & Playbook & PPTX ----
    if "stages" in st.session_state:
        if competitor != "None":
            bench = {
              "Visa":["Prospecting","KYC Check","Regulatory Review"],
              "Stripe":["API Integration Pilot","Sandbox Testing"],
              "Amex":["Regulatory Compliance","Fraud Assessment"]
            }
            st.markdown(f"#### Benchmark vs {competitor}")
            st.write(bench.get(competitor, []))

        if crm_file:
            df = pd.read_csv(crm_file)
            play=[]
            for _,row in df.iterrows():
                tipq=f"Lead data: {row.to_dict()}. Suggest next step."
                ans=client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role":"user","content":tipq}],
                    temperature=0.7,max_tokens=100
                ).choices[0].message.content
                play.append({**row.to_dict(),"suggestion":ans})
            st.markdown("#### Personalized Playbook from CRM")
            st.dataframe(pd.DataFrame(play))

        if pptx_ok and "tips" in st.session_state:
            prs=Presentation()
            sl=prs.slides.add_slide(prs.slide_layouts[0])
            sl.shapes.title.text=f"Floww Playbook: {company}"
            for s in st.session_state["stages"]:
                sld=prs.slides.add_slide(prs.slide_layouts[1])
                sld.shapes.title.text=s
                sld.placeholders[1].text=st.session_state['tips'][s]
            buf=io.BytesIO(); prs.save(buf); buf.seek(0)
            st.download_button("Download PPTX Playbook", buf,
                "floww_playbook.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation")

# -----------------------------------------------------#
#                      PROPOSAL TAB                    #
# -----------------------------------------------------#
with tab_prop:
    st.subheader("Generate Proposal")

    # ---- Client basics ----
    col1,col2=st.columns(2)
    with col1:
        client_name=st.text_input("Proposal for (client)", key="client")
    with col2:
        prop_date = st.date_input("Date", date.today())

    deliverables_txt = st.text_area(
        "Key deliverables (one per line)",
        placeholder="Integration setup\n24/7 support\nTraining sessions",
        height=100
    )

    # ---- Pricing data_editor ----
    st.markdown("#### Pricing Table")
    if "price_table" not in st.session_state:
        st.session_state["price_table"]=pd.DataFrame(
            [{"Item":"Integration","Qty":1,"Unit":"Lot","Unit Price":10000}]
        )

    # Preset buttons
    p1,p2,p3=st.columns(3)
    with p1:
        if st.button("🌱 Starter"):
            st.session_state["price_table"]=pd.DataFrame([
                {"Item":"Discovery","Qty":1,"Unit":"Lot","Unit Price":5000},
                {"Item":"Integration","Qty":1,"Unit":"Lot","Unit Price":20000},
            ])
    with p2:
        if st.button("🚀 Growth"):
            st.session_state["price_table"]=pd.DataFrame([
                {"Item":"Discovery","Qty":1,"Unit":"Lot","Unit Price":10000},
                {"Item":"Integration","Qty":1,"Unit":"Lot","Unit Price":50000},
                {"Item":"Training","Qty":1,"Unit":"Lot","Unit Price":15000},
            ])
    with p3:
        if st.button("🏢 Enterprise"):
            st.session_state["price_table"]=pd.DataFrame([
                {"Item":"Enterprise License (12 mo)","Qty":1,"Unit":"Lot","Unit Price":120000},
                {"Item":"Dedicated CSM","Qty":1,"Unit":"Yr","Unit Price":30000},
            ])

    price_df = st.data_editor(
        st.session_state["price_table"],
        num_rows="dynamic",
        use_container_width=True,
        key="price_editor"
    )
    price_df["Subtotal"]=price_df["Qty"]*price_df["Unit Price"]
    total = price_df["Subtotal"].sum()
    st.metric("Grand Total", f"${total:,.0f}")

    # ---- Generate proposal ----
    if st.button("Generate Proposal", type="primary"):
        with st.spinner("Crafting proposal with Floww AI …"):
            sys_p = ("You are an expert sales engineer. "
                     "Return ONLY valid JSON with keys: "
                     "title, executive_summary, background, solution_overview, "
                     "deliverables, pricing, next_steps.")
            usr_p = json.dumps({
                "client": client_name,
                "company": company,
                "date": str(prop_date),
                "deliverables": deliverables_txt.splitlines(),
                "pricing": price_df[["Item","Qty","Unit","Unit Price"]].to_dict(orient="records"),
                "total": total
            })
            prop_raw = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":sys_p},
                          {"role":"user","content":usr_p}],
                temperature=0.2, max_tokens=750
            ).choices[0].message.content
        try:
            prop = ProposalModel.parse_raw(prop_raw)
        except ValidationError as e:
            st.error("AI returned invalid JSON"); st.code(prop_raw); st.error(str(e)); st.stop()

        st.success("Proposal generated ✔︎")
        st.markdown(f"## {prop.title}")
        st.markdown(f"### Executive Summary\n{prop.executive_summary}")
        st.markdown(f"### Background\n{prop.background}")
        st.markdown(f"### Solution Overview\n{prop.solution_overview}")
        st.markdown("### Deliverables")
        st.markdown("\n".join([f"- {d}" for d in prop.deliverables]))
        st.markdown("### Pricing")
        display_df = pd.DataFrame(prop.pricing)
        st.table(display_df)
        st.markdown(f"### Next Steps\n{prop.next_steps}")

        # ---- PDF export ----
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        w,h = letter; y=h-40
        def add_text(txt, indent=40, leading=14):
            nonlocal y
            for line in txt.split('\\n'):
                c.drawString(indent,y,line); y-=leading
                if y<60: c.showPage(); y=h-40
        c.setFont("Helvetica-Bold",16); c.drawString(40,y, prop.title); y-=25
        c.setFont("Helvetica",12)
        for sec in ["executive_summary","background","solution_overview","next_steps"]:
            c.setFont("Helvetica-Bold",12); add_text(sec.replace('_',' ').title()+\":\",40); y-=5
            c.setFont("Helvetica",12); add_text(getattr(prop,sec),50); y-=10
        c.setFont("Helvetica-Bold",12); add_text("Pricing:",40); y-=5
        for r in display_df.itertuples(index=False):
            add_text(f\"{r.Item} x{r.Qty} {r.Unit}  …  ${r._4:,.0f}\",50)\n            y-=5
        add_text(f\"Grand Total: ${total:,.0f}\",50)\n        c.save(); buf.seek(0)\n        st.download_button(\"Download Proposal PDF\", buf, \"proposal.pdf\", \"application/pdf\")\n\n# ── Footer ───────────────────────────────────────────\nst.sidebar.markdown(\"---\")\nst.sidebar.markdown(\"Powered by Adam Cigri & OpenAI\")```
