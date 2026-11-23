"""Streamlit interface for the Company Research Agent."""

import os
import streamlit as st
from dotenv import load_dotenv

from search import research_company
from ai_processor import generate_report
from pdf_generator import generate_pdf

load_dotenv()

st.set_page_config(page_title="Company Research Agent", page_icon="🏢", layout="wide")

st.markdown("""
<style>
.main { background: #F8FAFC; }
.block-container { max-width: 1180px; padding-top: 2rem; }
.hero { background: linear-gradient(135deg,#0F172A,#1D4ED8); color:white; padding:28px 32px; border-radius:18px; margin-bottom:20px; }
.hero h1 { color:white; margin:0; font-size:2.1rem; }
.hero p { color:#DBEAFE; margin:8px 0 0 0; font-size:1.05rem; }
.card { background:white; border:1px solid #E2E8F0; border-radius:14px; padding:18px; margin-bottom:12px; box-shadow:0 3px 12px rgba(15,23,42,.04); }
.disclaimer { background:#FFF7ED; color:#9A3412; border:1px solid #FED7AA; border-radius:10px; padding:10px 14px; }
[data-testid="stSidebar"] { background:#F1F5F9; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🏢 Project Information")
    st.caption("AI & Automation Internship Practical Assignment")
    st.markdown("**Company Research Agent**")
    st.write("Uses Tavily for public web evidence and Gemini for structured report synthesis.")
    st.markdown("### Workflow")
    st.write("1. Search official and credible sources\n2. Validate source URLs\n3. Generate a cited report\n4. Export a PDF")
    st.markdown("### API status")
    st.write("Tavily:", "Configured" if os.getenv("TAVILY_API_KEY") else "Not configured")
    st.write("Gemini:", "Configured" if os.getenv("GEMINI_API_KEY") else "Not configured")

st.markdown('<div class="hero"><h1>Company Research Agent</h1><p>AI-powered company intelligence and meeting preparation</p></div>', unsafe_allow_html=True)
st.markdown('<div class="disclaimer">⚠️ Information is compiled from publicly available sources. Please independently verify important details.</div>', unsafe_allow_html=True)

st.markdown("### Research a company")
col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
with col1:
    company_name = st.text_input("Company name", placeholder="e.g. Microsoft Corporation", label_visibility="collapsed")
with col2:
    search_clicked = st.button("🔍 Research Company", use_container_width=True, type="primary")

if search_clicked:
    company_name = company_name.strip()
    if len(company_name) < 2:
        st.error("Please enter a valid company name.")
    else:
        try:
            with st.status("Researching public sources and preparing report...", expanded=False) as status:
                st.write("Searching company overview and public sources...")
                results = research_company(company_name)
                st.write(f"Found {len(results)} relevant unique sources.")
                st.write("Using Gemini to synthesize evidence...")
                report = generate_report(company_name, results)
                status.update(label="Research complete", state="complete")

            st.session_state["report"] = report
            st.session_state["company_name"] = company_name
        except ValueError as exc:
            st.error(str(exc))
            st.info("Add TAVILY_API_KEY and GEMINI_API_KEY to your local .env file or Streamlit Cloud secrets.")
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception:
            st.error("An unexpected error occurred while generating the report. Please verify API keys and try again.")

if "report" in st.session_state:
    report = st.session_state["report"]
    st.markdown(f"## Research Report: {report.get('company_name', st.session_state.get('company_name', 'Company'))}")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Company Overview", "Company Size & Locations", "Recent News",
        "Key Decision-Makers", "Talking Points", "Sources & References"
    ])

    unavailable = "Not publicly available"

    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### What the company does")
        st.write(report.get("overview") or unavailable)
        st.markdown("### Industry")
        st.write(report.get("industry") or unavailable)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### Employee size")
        st.write(report.get("employee_size") or unavailable)
        st.markdown("### Headquarters")
        st.write(report.get("headquarters") or unavailable)
        st.markdown("### Office locations")
        locations = report.get("locations", [])
        if locations:
            for location in locations:
                st.write(f"• {location}")
        else:
            st.write(unavailable)
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        news = report.get("recent_news", [])
        if news:
            for item in news:
                if not isinstance(item, dict):
                    continue
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(f"### {item.get('headline') or unavailable}")
                st.caption(item.get("date") or unavailable)
                st.write(item.get("summary") or unavailable)
                urls = item.get("source_urls", [])
                if urls:
                    for url in urls:
                        st.markdown(f"[Source]({url})")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info(unavailable)

    with tab4:
        people = report.get("decision_makers", [])
        if people:
            for person in people:
                if not isinstance(person, dict):
                    continue
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(f"### {person.get('name') or unavailable}")
                st.write(f"**Designation:** {person.get('designation') or unavailable}")
                st.write(f"**Public professional contact:** {person.get('contact') or unavailable}")
                for url in person.get("source_urls", []) or []:
                    st.markdown(f"[Supporting source]({url})")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info(unavailable)

    with tab5:
        points = report.get("talking_points", [])
        if points:
            for index, point in enumerate(points, start=1):
                if not isinstance(point, dict):
                    continue
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown(f"### {index}. Meeting Talking Point")
                st.write(point.get("point") or unavailable)
                for url in point.get("source_urls", []) or []:
                    st.markdown(f"[Supporting source]({url})")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info(unavailable)

    with tab6:
        sources = report.get("sources", [])
        if sources:
            for index, url in enumerate(sources, start=1):
                st.markdown(f"{index}. [{url}]({url})")
        else:
            st.info(unavailable)

    try:
        pdf_bytes = generate_pdf(report)
        st.download_button(
            "📄 Download PDF Report",
            data=pdf_bytes,
            file_name=f"{report.get('company_name', 'company')}-research-report.pdf".replace(" ", "-").lower(),
            mime="application/pdf",
            use_container_width=False,
        )
    except Exception:
        st.error("The PDF could not be generated. The on-screen report is still available.")
