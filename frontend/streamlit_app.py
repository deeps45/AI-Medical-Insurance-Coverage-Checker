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

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
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


def fetch_documents() -> list[dict]:
    try:
        response = requests.get(f"{BASE_URL}/documents", timeout=10)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        return []
    return []


def init_state() -> None:
    defaults = {
        "document_info": None,
        "qa_history": [],
        "example_question": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def history_transcript() -> str:
    lines = []
    for item in reversed(st.session_state.qa_history):
        lines.append(f"Q: {item['question']}")
        lines.append(f"A: {item['answer']}")
        if item.get("sources"):
            src = ", ".join(
                f"{s.get('source', '?')} p{s.get('page', '?')}" for s in item["sources"]
            )
            lines.append(f"Sources: {src}")
        lines.append(f"Latency: {item['latency_ms']:.0f} ms")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


init_state()

with st.sidebar:
    st.markdown("### Coverage Checker")
    st.caption("Understand your medical insurance policy in plain language.")

    health = check_backend()
    if health:
        st.success("Backend connected")
        st.caption(
            f"LLM: `{health.get('llm_provider', '?')}` · "
            f"model: `{health.get('chat_model') or 'n/a'}` · "
            f"vectors: `{health.get('vectorstore', '?')}` · "
            f"DB: `{health.get('database', '?')}`"
        )
    else:
        st.error("Backend offline")
        st.info(f"Expected at `{BASE_URL}`")
        st.stop()

    st.divider()
    st.markdown("**Recent documents**")
    docs = fetch_documents()
    if docs:
        labels = {
            f"{d['filename']} ({d['page_count']}p · {d['id'][:8]}…)": d for d in docs[:15]
        }
        choice = st.selectbox("Load a previous upload", ["—"] + list(labels.keys()))
        if choice != "—" and st.button("Use selected document", use_container_width=True):
            selected = labels[choice]
            st.session_state.document_info = {
                "document_id": selected["id"],
                "pages": selected["page_count"],
                "chunks": selected.get("chunk_count", 0),
                "filename": selected["filename"],
            }
            st.session_state.qa_history = []
            st.rerun()
    else:
        st.caption("No documents yet.")

    st.divider()
    st.markdown("**Tips**")
    st.markdown(
        "- Upload the full policy PDF\n"
        "- Ask about copays, deductibles, exclusions\n"
        "- Answers cite page numbers when possible"
    )
    st.warning(
        "Assistive only — not official benefits advice. "
        "Verify with your insurer or plan documents."
    )

st.title("Medical Insurance Coverage Checker")
st.markdown(
    "Upload a policy PDF, then ask questions about coverage, copays, and benefits."
)

st.subheader("1. Upload policy")
uploaded_file = st.file_uploader("Insurance policy PDF", type=["pdf"])

if st.button("Process PDF", type="primary", disabled=uploaded_file is None):
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
    if info.get("filename"):
        st.caption(f"Active file: **{info['filename']}**")

st.subheader("2. Ask about coverage")

if not info:
    st.info("Upload and process a PDF (or pick a recent document in the sidebar).")
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

c1, c2, c3 = st.columns([1, 1, 2])
ask = c1.button("Ask", type="primary", disabled=not question.strip())
if c2.button("Clear history", disabled=not st.session_state.qa_history):
    st.session_state.qa_history = []
    st.rerun()

if ask and question.strip():
    with st.spinner("Searching policy and drafting answer..."):
        try:
            payload = {
                "question": question.strip(),
                "k": k_chunks,
                "document_id": info["document_id"],
            }
            response = requests.post(f"{BASE_URL}/ask", json=payload, timeout=90)
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

if st.session_state.qa_history:
    st.download_button(
        "Download Q&A transcript",
        data=history_transcript(),
        file_name="coverage-qa.txt",
        mime="text/plain",
    )

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

st.caption("Coverage Checker · TAMU Chat / OpenAI · Pinecone/FAISS · Streamlit")
