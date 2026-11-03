import pandas as pd
import streamlit as st
from scoring import score_lead, WEIGHTS, HOT_MIN, WARM_MIN, FIELDS
from llm_explainer import llm_explanation

st.set_page_config(page_title="Lead Scoring", page_icon="🎯", layout="wide")
SAMPLE = dict(name="Rahul Sharma", company="ABC Technologies", website="www.abctechnologies.com",
              job_title="Founder", industry="IT Services", location="Bangalore",
              company_size="50-100 Employees", lead_source="Website",
              requirement="Looking for CRM software", email="rahul@example.com", phone="+91 9876543210")
COLORS = {"Hot": "#d64545", "Warm": "#e69f00", "Cold": "#3b7dd8"}

st.title("AI-Based Lead Scoring")
st.caption("Scores come from a transparent weighted rule engine. The LLM only writes the explanation.")

with st.sidebar:
    st.header("Scoring weights")
    st.table(pd.DataFrame({"Parameter": list(WEIGHTS), "Points": list(WEIGHTS.values())}))
    st.write(f"**Hot** ≥ {HOT_MIN} · **Warm** {WARM_MIN}-{HOT_MIN-1} · **Cold** < {WARM_MIN}")
    use_llm = st.toggle("Use LLM for explanation", value=False,
                        help="Needs ANTHROPIC_API_KEY. Score is unaffected.")


def show(lead, r):
    c = COLORS[r["classification"]]
    a, b, d, e = st.columns(4)
    a.metric("Lead score", f"{r['score']}/100")
    b.markdown(f"**Classification**<br><span style='font-size:2rem;color:{c};font-weight:700'>{r['classification']}</span>", unsafe_allow_html=True)
    d.metric("Quality", r["quality"])
    e.metric("Confidence", r["confidence"], f"{int(r['completeness']*100)}% data complete", delta_color="off")
    st.progress(r["score"] / 100)
    st.subheader("Recommended next action")
    st.info(r["next_action"])
    l, rt = st.columns(2)
    l.subheader("✅ Positive factors")
    for p in r["positives"] or ["None"]: l.write("• " + p)
    rt.subheader("⚠️ Negative factors")
    for n in r["negatives"] or ["None"]: rt.write("• " + n)
    st.subheader("Score breakdown")
    df = pd.DataFrame(r["factors"]).rename(columns={"name": "Parameter", "weight": "Max", "earned": "Earned",
                                                    "value": "Input", "note": "Reasoning", "impact": "Impact"})
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.bar_chart(df.set_index("Parameter")[["Earned", "Max"]])
    st.subheader("Scoring explanation")
    st.write(r["explanation"])
    if use_llm:
        with st.spinner("Asking LLM for analysis..."):
            text, err = llm_explanation(lead, r)
        st.markdown("**LLM analysis**")
        st.write(text) if text else st.warning(err)


tab1, tab2 = st.tabs(["Single lead", "Batch (CSV)"])
with tab1:
    with st.form("lead"):
        c1, c2, c3 = st.columns(3)
        lead = {}
        labels = {"name": "Name", "company": "Company name", "website": "Website", "job_title": "Job title",
                  "industry": "Industry", "location": "Company location", "company_size": "Company size",
                  "lead_source": "Lead source", "requirement": "Requirement", "email": "Email", "phone": "Phone"}
        for i, k in enumerate(FIELDS):
            lead[k] = [c1, c2, c3][i % 3].text_input(labels[k], SAMPLE[k])
        go = st.form_submit_button("Score lead", type="primary")
    if go:
        show(lead, score_lead(lead).to_dict())
with tab2:
    st.write("Upload a CSV with columns: " + ", ".join(FIELDS))
    up = st.file_uploader("CSV file", type="csv")
    if up:
        df = pd.read_csv(up).fillna("")
        rows = []
        for rec in df.to_dict("records"):
            r = score_lead(rec)
            rows.append({"name": rec.get("name", ""), "company": rec.get("company", ""), "score": r.score,
                         "classification": r.classification, "confidence": r.confidence, "next_action": r.next_action})
        out = pd.DataFrame(rows).sort_values("score", ascending=False)
        st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button("Download results", out.to_csv(index=False), "scored_leads.csv", "text/csv")
