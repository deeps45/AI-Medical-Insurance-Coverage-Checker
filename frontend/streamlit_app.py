"""Streamlit frontend for AI Medical Insurance Coverage Checker."""

from __future__ import annotations

import os
import time

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = (
    "http://localhost:8001" if os.getenv("RENDER") != "true" else "http://localhost:8000"
)
BASE_URL = os.getenv("BASE_URL", DEFAULT_BASE_URL)

st.set_page_config(
    page_title="Coverage Checker",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Styles ---
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      .answer-box {
        background: #f7fafc;
        border-left: 4px solid #0d9488;
        padding: 1rem 1.25rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0 1rem;
      }
      .source-chip {
        display: inline-block;
        background: #ecfeff;
        color: #0f766e;
        padding: 0.15rem 0.55rem;
        border-radius: 4px;
        margin: 0.15rem 0.25rem 0.15rem 0;
        font-size: 0.85rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def check_backend() -> dict | None:
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        return None
    return None


def init_state() -> None:
    defaults = {
        "document_info": None,
        "qa_history": [],
        "example_question": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Coverage Checker")
    st.caption("Understand your medical insurance policy in plain language.")

    health = check_backend()
    if health:
        st.success("Backend connected")
        st.caption(
            f"Vector store: `{health.get('vectorstore', '?')}` · "
            f"DB: `{health.get('database', '?')}`"
        )
    else:
        st.error("Backend offline")
        st.info(f"Expected at `{BASE_URL}`")
        st.stop()

    st.divider()
    st.markdown("**Tips**")
    st.markdown(
        "- Upload the full policy PDF\n"
        "- Ask about copays, deductibles, exclusions\n"
        "- Answers cite page numbers when possible"
    )

# --- Header ---
st.title("Medical Insurance Coverage Checker")
st.markdown(
    "Upload a policy PDF, then ask questions about coverage, copays, and benefits."
)

# --- Upload ---
st.subheader("1. Upload policy")
uploaded_file = st.file_uploader("Insurance policy PDF", type=["pdf"])

col_a, col_b = st.columns([1, 3])
with col_a:
    process = st.button("Process PDF", type="primary", disabled=uploaded_file is None)

if process and uploaded_file is not None:
    with st.spinner("Extracting text and building search index..."):
        try:
            files = {
                "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")
            }
            response = requests.post(f"{BASE_URL}/ingest", files=files, timeout=120)
            if response.status_code == 200:
                result = response.json()
                st.session_state.document_info = result
                st.session_state.qa_history = []
                st.success(
                    f"Processed **{result.get('filename', uploaded_file.name)}** — "
                    f"{result['pages']} pages, {result['chunks']} chunks"
                )
            else:
                st.error(f"Processing failed: {response.text}")
        except requests.RequestException as exc:
            st.error(f"Could not reach backend: {exc}")

info = st.session_state.document_info
if info:
    m1, m2, m3 = st.columns(3)
    m1.metric("Pages", info["pages"])
    m2.metric("Chunks", info["chunks"])
    m3.metric("Document", info["document_id"][:8] + "…")

# --- Ask ---
st.subheader("2. Ask about coverage")

if not info:
    st.info("Upload and process a PDF to enable questions.")
    st.stop()

examples = [
    "Is MRI covered under this policy?",
    "What's the copay for emergency room visits?",
    "What's the annual deductible?",
    "Are prescription drugs covered?",
    "What's the out-of-pocket maximum?",
    "Is physical therapy covered?",
]

with st.expander("Example questions", expanded=not st.session_state.qa_history):
    cols = st.columns(2)
    for i, example in enumerate(examples):
        if cols[i % 2].button(example, key=f"ex_{i}", use_container_width=True):
            st.session_state.example_question = example
            st.rerun()

question = st.text_input(
    "Your question",
    value=st.session_state.example_question,
    placeholder="e.g. Is MRI covered? What's the ER copay?",
)

k_chunks = st.slider("Context passages to retrieve", 1, 10, 4, key="k_slider")

ask = st.button("Ask", type="primary", disabled=not question.strip())

if ask and question.strip():
    with st.spinner("Searching policy and drafting answer..."):
        try:
            payload = {
                "question": question.strip(),
                "k": k_chunks,
                "document_id": info["document_id"],
            }
            response = requests.post(f"{BASE_URL}/ask", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                st.session_state.qa_history.insert(
                    0,
                    {
                        "question": question.strip(),
                        "answer": result["answer"],
                        "latency_ms": result["latency_ms"],
                        "sources": result.get("sources", []),
                        "ts": time.strftime("%H:%M:%S"),
                    },
                )
                st.session_state.example_question = ""
            else:
                st.error(f"Ask failed: {response.text}")
        except requests.RequestException as exc:
            st.error(f"Could not reach backend: {exc}")

# --- History ---
for item in st.session_state.qa_history:
    st.markdown(f"**Q:** {item['question']}")
    st.info(item["answer"])
    if item.get("sources"):
        source_labels = [
            f"{s.get('source', '?')} · p{s.get('page', '?')}" for s in item["sources"]
        ]
        st.caption("Sources: " + " · ".join(source_labels))
    st.caption(f"{item['latency_ms']:.0f} ms · {item['ts']}")
    st.divider()

st.caption("Coverage Checker · LangChain · OpenAI · Pinecone/FAISS")
