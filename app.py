"""TalentParse: upload or paste a resume, review the auto-filled candidate form, export JSON."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from hr_parser import LLMUnavailable, ParseError, extract_text_from_pdf, parse_resume
from hr_parser.llm_client import get_llm
from hr_parser.schemas import count_filled, is_valid_email, new_profile, normalize_profile

ROOT = Path(__file__).parent
OUTPUT_FILE = ROOT / "output" / "candidates.json"
SAMPLE_TEXT = (ROOT / "sample" / "sample_resume.txt").read_text(encoding="utf-8")
EDU_COLUMNS = ["degree", "institution", "year"]
EXP_COLUMNS = ["role", "company", "years"]

load_dotenv()
st.set_page_config(page_title="TalentParse", layout="wide")
st.markdown(f"<style>{(ROOT / 'assets' / 'style.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)

if "profile" not in st.session_state:
    st.session_state.profile = new_profile()
    st.session_state.version = 0  # bumping it gives every form widget a fresh key, so it re-fills
    st.session_state.filled = 0


def to_frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    return frame.fillna("").astype(str).replace({"None": ""})


def save_candidate(profile: dict) -> None:
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    saved = json.loads(OUTPUT_FILE.read_text(encoding="utf-8")) if OUTPUT_FILE.exists() else []
    saved.append({"saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **profile})
    OUTPUT_FILE.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------- sidebar: LLM settings ----------
with st.sidebar:
    st.header("Settings")
    has_server = bool(os.getenv("LLM_URL"))
    backend = st.radio("LLM backend", ["Demo (no GPU)", "Remote LLM (Kaggle + ngrok)"],
                       index=1 if has_server else 0)
    server_url = server_token = ""
    if backend.startswith("Remote"):
        server_url = st.text_input("Server URL", value=os.getenv("LLM_URL", ""),
                                   placeholder="https://xxxx.ngrok-free.app")
        server_token = st.text_input("API key", value=os.getenv("LLM_TOKEN", ""), type="password")
    else:
        st.caption("Demo mode understands the lab's sample format only. "
                   "Use the remote LLM for real resumes.")

st.markdown('<div class="brand"><span class="logo"></span>TalentParse</div>', unsafe_allow_html=True)
left, right = st.columns([1, 2], gap="large")

# ---------- step 1: import ----------
with left, st.container(border=True):
    st.subheader("1. Import resume")
    source = st.radio("Source", ["Paste text", "Upload PDF"], horizontal=True,
                      label_visibility="collapsed")
    pasted, pdf = "", None
    if source == "Paste text":
        pasted = st.text_area("Resume snippet", value=SAMPLE_TEXT, height=300)
    else:
        pdf = st.file_uploader("Resume PDF", type="pdf")
    run = st.button("Auto-fill the form", type="primary", use_container_width=True)

if run:
    try:
        if source == "Upload PDF" and pdf is None:
            raise ParseError("Upload a PDF first.")
        text = extract_text_from_pdf(pdf) if source == "Upload PDF" else pasted
        llm = get_llm("demo" if backend.startswith("Demo") else "remote", server_url, server_token)
        with st.spinner("Reading the resume..."):
            profile = parse_resume(text, llm)
        st.session_state.profile = profile
        st.session_state.version += 1
        st.session_state.filled = count_filled(profile)
    except (ParseError, LLMUnavailable) as error:
        left.error(str(error))

# ---------- step 2: review the auto-filled form ----------
profile, version = st.session_state.profile, st.session_state.version
with right, st.container(border=True):
    title_col, badge_col = st.columns([3, 2])
    title_col.subheader("2. Review candidate profile")
    if st.session_state.filled:
        badge_col.markdown(f'<span class="badge">{st.session_state.filled} fields auto-filled · '
                           'edit anything</span>', unsafe_allow_html=True)
    else:
        st.caption("Paste a resume on the left and press Auto-fill the form, or type the details yourself.")

    name_col, email_col = st.columns(2)
    full_name = name_col.text_input("Full name", value=profile["full_name"], key=f"name_{version}")
    email = email_col.text_input("Email", value=profile["email"], key=f"email_{version}")
    if email and not is_valid_email(email):
        email_col.caption("Check the email format.")

    st.markdown("**Education**")
    education = st.data_editor(
        to_frame(profile["education"], EDU_COLUMNS), num_rows="dynamic", hide_index=True,
        use_container_width=True, key=f"edu_{version}",
        column_config={"degree": st.column_config.TextColumn("Degree", width="large"),
                       "institution": st.column_config.TextColumn("Institution", width="large"),
                       "year": st.column_config.TextColumn("Year", width="small")})

    st.markdown("**Skills**")
    skills = st.multiselect("Skills", options=profile["skills"], default=profile["skills"],
                            accept_new_options=True, key=f"skills_{version}",
                            label_visibility="collapsed", placeholder="Type a skill and press Enter")

    st.markdown("**Experience**")
    experience = st.data_editor(
        to_frame(profile["experience"], EXP_COLUMNS), num_rows="dynamic", hide_index=True,
        use_container_width=True, key=f"exp_{version}",
        column_config={"role": st.column_config.TextColumn("Role", width="large"),
                       "company": st.column_config.TextColumn("Company", width="large"),
                       "years": st.column_config.TextColumn("Years", width="medium")})

    # The form is the source of truth: rebuild the JSON from what is on screen.
    result = normalize_profile({
        "full_name": full_name, "email": email, "skills": skills,
        "education": education.to_dict("records"), "experience": experience.to_dict("records"),
    })
    download_col, save_col = st.columns(2)
    download_col.download_button(
        "Download .json", data=json.dumps(result, indent=2, ensure_ascii=False),
        file_name=f"{(result['full_name'] or 'candidate').lower().replace(' ', '_')}.json",
        mime="application/json", use_container_width=True)
    if save_col.button("Save candidate", type="primary", use_container_width=True):
        if not result["full_name"]:
            st.warning("Enter the candidate's name before saving.")
        else:
            save_candidate(result)
            st.success(f"Saved {result['full_name']} to output/candidates.json")
