import os
from typing import List

import streamlit as st

from wobd_web import __doc__ as wobd_web_doc
from wobd_web.config import CONFIG_ENV_VAR, load_config
from wobd_web.executor import run_plan
from wobd_web.models import AnswerBundle
from wobd_web.router import build_query_plan
from wobd_web.nl_to_sparql import set_openai_api_key


# EXAMPLE_QUESTIONS: List[str] = [
#     "What studies are available for COVID-19?",
#     "List gene expression datasets involving lung tissue.",
#     "Which datasets include pediatric participants?",
#     "Show datasets related to influenza vaccines.",
#     "Find datasets with RNA-seq data for human blood samples.",
#     "Which datasets link clinical outcomes to gene expression?",
# ]

EXAMPLE_QUESTIONS: List[str] = [
    "Show datasets related to influenza vaccines.",
    "Find datasets with RNA-seq data for human blood samples.",
    "Find datasets that use an experimental system that might be useful for studying the drug Tocilizumab.",
    "Find experiments where Dusp2 is upregulated.",
]

def _init_session_state() -> None:
    if "history" not in st.session_state:
        st.session_state["history"] = []  # list[tuple[str, AnswerBundle | str]]


def main() -> None:
    """Streamlit entrypoint for the WOBD web app."""

    st.set_page_config(page_title="WOBD Web", layout="wide")
    _init_session_state()

    # Check for OpenAI API key (Streamlit secrets or environment variable)
    try:
        OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    except (FileNotFoundError, AttributeError, KeyError):
        # Fall back to environment variable if secrets not available (e.g., local development)
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not OPENAI_API_KEY:
        st.error("Missing OPENAI_API_KEY. Set it in Streamlit Community Cloud → App Settings → Secrets, or as an environment variable.")
        st.stop()
    
    # Set the API key for the NL→SPARQL module
    set_openai_api_key(OPENAI_API_KEY)

    cfg = load_config()

    st.title("WOBD Web")
    st.caption(
        f"Config: {os.environ.get(CONFIG_ENV_VAR, 'web/configs/demo.local.yaml')} | "
        f"LLM model: {cfg.llm.model}"
    )

    # Sidebar controls
    with st.sidebar:
        st.header("Options")
        show_sparql = st.checkbox(
            "Show generated SPARQL", value=cfg.ui.show_generated_sparql
        )
        show_provenance = st.checkbox(
            "Show provenance", value=cfg.ui.show_provenance
        )
        
        apply_query_limit = st.checkbox(
            "Apply query limit", value=True,
            help="Limit query results to max_rows (from config). Disable to get all results."
        )

        st.markdown("### Example questions")
        for q in EXAMPLE_QUESTIONS:
            if st.button(q, key=f"example-{q}"):
                # Drive the main text input directly via its session key so
                # the value is reflected immediately in the UI.
                st.session_state["question_input"] = q

    # Main chat interface
    question = st.text_area(
        "Ask a question about the data:",
        key="question_input",
        height=100,
        help="Type your question here. You can resize this box by dragging the bottom-right corner.",
    )
    col_submit, col_clear = st.columns([1, 1])
    with col_submit:
        run_clicked = st.button("Submit", type="primary")
    with col_clear:
        clear_clicked = st.button("Clear history")

    if clear_clicked:
        st.session_state["history"] = []

    answer_bundle: AnswerBundle | None = None
    if run_clicked and question.strip():
        with st.spinner("Generating queries and fetching results..."):
            plan = build_query_plan(question=question.strip())
            answer_bundle = run_plan(plan, question=question.strip(), apply_limit=apply_query_limit)
            st.session_state["history"].append((question.strip(), answer_bundle))

    # Display chat history
    for prev_question, prev_answer in st.session_state["history"]:
        st.markdown(f"**You:** {prev_question}")
        if isinstance(prev_answer, AnswerBundle):
            st.markdown(f"**Answer:** {prev_answer.final_text}")

    if answer_bundle is not None:
        st.markdown("### Latest answer")
        st.write(answer_bundle.final_text)
        
        # Show note about limit if it was applied
        if answer_bundle.limit_applied and answer_bundle.limit_value:
            st.info(f"ℹ️ Results limited to {answer_bundle.limit_value} rows. Uncheck 'Apply query limit' in the sidebar to get all results, or include keywords like 'all results' or 'no limit' in your question.")

        # Tabs per source
        if answer_bundle.tables:
            tab_labels = list(answer_bundle.tables.keys())
            tabs = st.tabs(tab_labels)
            for label, tab in zip(tab_labels, tabs):
                with tab:
                    rows = answer_bundle.tables.get(label, [])
                    st.write(f"{len(rows)} row(s)")
                    if rows:
                        st.dataframe(rows)

        if show_sparql and answer_bundle.sparql_texts:
            with st.expander("Generated SPARQL"):
                for src, sparql in answer_bundle.sparql_texts.items():
                    st.markdown(f"**{src}**")
                    st.code(sparql, language="sparql")

        if show_provenance and answer_bundle.provenance:
            with st.expander("Provenance"):
                prov_rows = [
                    {
                        "source": p.source_label,
                        "endpoint": p.endpoint_url,
                        "elapsed_ms": round(p.elapsed_ms, 1),
                        "row_count": p.row_count,
                        "status": p.status,
                    }
                    for p in answer_bundle.provenance
                ]
                st.dataframe(prov_rows)

    with st.expander("About this app"):
        st.write(wobd_web_doc or "OKN-WOBD web interface components.")


if __name__ == "__main__":
    main()

