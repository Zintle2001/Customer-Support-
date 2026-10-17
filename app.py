import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "experiments.db"
SAMPLE_PATH = APP_DIR / "data" / "sample_messages.csv"

DEFAULT_PROMPTS = {
    "Prompt 1 — Basic": """You are a helpful e-commerce customer support agent.
Reply to the customer's message politely and helpfully.

Customer message:
{customer_message}""",
    "Prompt 2 — Structured": """You are an e-commerce customer support agent. Write a clear, helpful response.
Follow this structure:
1. Acknowledge the customer's concern.
2. Explain what information or next step is needed.
3. End with a polite offer of further help.
Do not invent order details, refund eligibility, or actions already taken.

Customer message:
{customer_message}""",
    "Prompt 3 — Empathetic and concise": """Act as a calm, empathetic e-commerce customer support agent.
Rules:
- Be polite and acknowledge the customer's specific concern.
- Keep the response concise and easy to understand.
- Do not promise a refund or claim an action has been completed unless the customer message provides evidence.
- If key details are missing, ask for them.
- Give a practical next step.

Customer message:
{customer_message}"""
}
CRITERIA = ["Relevance", "Politeness", "Completeness"]

def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        customer_message TEXT NOT NULL,
        prompt_name TEXT NOT NULL,
        prompt_text TEXT NOT NULL,
        model TEXT NOT NULL,
        response TEXT NOT NULL,
        relevance INTEGER,
        politeness INTEGER,
        completeness INTEGER,
        notes TEXT
    )""")
    conn.commit()
    return conn

def save_run(conn, message, prompt_name, prompt_text, model, response, scores, notes):
    conn.execute(
        """INSERT INTO runs
        (created_at, customer_message, prompt_name, prompt_text, model, response,
         relevance, politeness, completeness, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now(timezone.utc).isoformat(), message, prompt_name, prompt_text,
         model, response, scores.get("Relevance"), scores.get("Politeness"),
         scores.get("Completeness"), notes)
    )
    conn.commit()

def log_to_comet(payload):
    """Optional Comet logging. Requires COMET_API_KEY and COMET_PROJECT_NAME."""
    if not os.getenv("COMET_API_KEY"):
        return False, "Comet not configured; run saved locally."
    try:
        from comet_ml import Experiment
        experiment = Experiment(
            project_name=os.getenv("COMET_PROJECT_NAME", "prompt-evaluation-dashboard"),
            auto_metric_logging=False,
            auto_param_logging=False,
        )
        experiment.set_name(payload["prompt_name"])
        experiment.log_parameter("model", payload["model"])
        experiment.log_parameter("prompt_name", payload["prompt_name"])
        experiment.log_text(payload["customer_message"], metadata={"kind": "customer_message"})
        experiment.log_text(payload["response"], metadata={"kind": "generated_response"})
        for key, value in payload["scores"].items():
            experiment.log_metric(key.lower(), value)
        experiment.log_metric("average_score", sum(payload["scores"].values()) / len(payload["scores"]))
        experiment.end()
        return True, "Logged to Comet."
    except Exception as exc:
        return False, f"Saved locally, but Comet logging failed: {exc}"

st.set_page_config(page_title="Prompt Evaluation Dashboard", page_icon="🧪", layout="wide")
st.title("🧪 Prompt Evaluation Dashboard")
st.caption("Compare customer-support prompts, score their responses, and track experiments.")

conn = connect_db()
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("OpenAI API key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    model = st.text_input("Model", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    st.caption("API usage may incur charges. Your key is used for requests from this app.")
    st.divider()
    st.subheader("Evaluation guide")
    st.markdown("- **1:** Poor / missing\n- **3:** Acceptable, with gaps\n- **5:** Excellent")
    st.caption("Scores are manual in Version 1. Do not enter real customer personal data.")

tab_run, tab_history, tab_prompts = st.tabs(["Run an evaluation", "Experiment history", "Prompt versions"])

with tab_prompts:
    st.subheader("Edit the three prompt versions")
    st.write("These starter prompts are editable for this session. Keep the `{customer_message}` placeholder.")
    prompt_texts = {}
    cols = st.columns(3)
    for i, (name, default) in enumerate(DEFAULT_PROMPTS.items()):
        with cols[i]:
            prompt_texts[name] = st.text_area(name, value=st.session_state.get("prompt_" + str(i), default), height=300, key="prompt_" + str(i))
    st.info("Prompt edits stay in the current Streamlit session. Saved runs retain the exact prompt text used.")

with tab_run:
    st.subheader("1. Enter a customer message")
    examples = []
    if SAMPLE_PATH.exists():
        try:
            examples = pd.read_csv(SAMPLE_PATH)["customer_message"].dropna().tolist()
        except Exception:
            pass
    choice = st.selectbox("Load a sample (optional)", ["Write my own"] + examples)
    default_message = "" if choice == "Write my own" else choice
    customer_message = st.text_area("Customer message", value=default_message, height=110,
                                    placeholder="Example: My order arrived damaged. Can I get a refund?")
    selected = st.multiselect("Prompts to compare", list(DEFAULT_PROMPTS.keys()), default=list(DEFAULT_PROMPTS.keys()))
    generate = st.button("Generate responses", type="primary", disabled=not customer_message.strip() or not selected)

    if generate:
        if not api_key:
            st.error("Add your OpenAI API key in the sidebar or set OPENAI_API_KEY in your .env file.")
        else:
            try:
                client = OpenAI(api_key=api_key)
                results = []
                progress = st.progress(0)
                for idx, name in enumerate(selected):
                    prompt = prompt_texts[name]
                    if "{customer_message}" not in prompt:
                        st.warning(f"{name} does not contain {{customer_message}}. The message will be appended.")
                        rendered = prompt + "\n\nCustomer message:\n" + customer_message
                    else:
                        rendered = prompt.replace("{customer_message}", customer_message)
                    with st.spinner(f"Generating with {name}..."):
                        response = client.responses.create(
                            model=model,
                            instructions="Follow the prompt exactly. Do not invent customer, order, or policy details.",
                            input=rendered,
                        )
                    output = response.output_text
                    results.append({"name": name, "prompt": prompt, "response": output})
                    progress.progress((idx + 1) / len(selected))
                st.session_state["latest_results"] = results
                st.session_state["latest_message"] = customer_message
                st.session_state["latest_model"] = model
            except Exception as exc:
                st.error(f"Generation failed: {exc}")

    results = st.session_state.get("latest_results", [])
    if results:
        st.subheader("2. Compare responses")
        st.caption("Read all responses before scoring them. The same customer message and model are used for this run.")
        response_cols = st.columns(len(results))
        for col, result in zip(response_cols, results):
            with col:
                st.markdown(f"**{result['name']}**")
                st.write(result["response"])
                with st.expander("View exact prompt"):
                    st.code(result["prompt"], language="text")
        st.subheader("3. Score each response")
        st.write("Score each criterion from 1 (poor) to 5 (excellent).")
        with st.form("score_form"):
            score_rows = {}
            score_cols = st.columns(len(results))
            for col, result in zip(score_cols, results):
                with col:
                    st.markdown(f"**{result['name']}**")
                    score_rows[result["name"]] = {}
                    for criterion in CRITERIA:
                        score_rows[result["name"]][criterion] = st.slider(
                            criterion, min_value=1, max_value=5, value=3,
                            key=f"score_{result['name']}_{criterion}"
                        )
                    score_rows[result["name"]]["Notes"] = st.text_input(
                        "Evaluator notes", key=f"notes_{result['name']}"
                    )
            save_clicked = st.form_submit_button("Save scores and log experiments", type="primary")
        if save_clicked:
            for result in results:
                scores = {c: score_rows[result["name"]][c] for c in CRITERIA}
                notes = score_rows[result["name"]]["Notes"]
                save_run(conn, st.session_state["latest_message"], result["name"], result["prompt"],
                         st.session_state["latest_model"], result["response"], scores, notes)
                ok, message = log_to_comet({
                    "prompt_name": result["name"], "model": st.session_state["latest_model"],
                    "customer_message": st.session_state["latest_message"],
                    "response": result["response"], "scores": scores
                })
                if ok:
                    st.success(f"{result['name']}: {message}")
                else:
                    st.warning(f"{result['name']}: {message}")
            st.success("Scores saved to the local SQLite database.")

with tab_history:
    st.subheader("Saved experiment runs")
    df = pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", conn)
    if df.empty:
        st.info("No saved runs yet. Generate responses and save scores in the first tab.")
    else:
        df["average_score"] = df[CRITERIA].mean(axis=1)
        st.metric("Saved response evaluations", len(df))
        summary = df.groupby("prompt_name")[CRITERIA + ["average_score"]].mean().round(2).reset_index()
        st.markdown("**Average scores by prompt**")
        st.dataframe(summary, use_container_width=True, hide_index=True)
        st.bar_chart(summary.set_index("prompt_name")["average_score"])
        st.markdown("**Individual evaluations**")
        st.dataframe(df[["created_at", "prompt_name", "customer_message", "relevance", "politeness",
                         "completeness", "average_score", "model", "notes"]], use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download experiment history as CSV", csv, "prompt_experiment_history.csv", "text/csv")
        if st.checkbox("Show full generated responses"):
            st.dataframe(df[["prompt_name", "customer_message", "response", "prompt_text"]], use_container_width=True)

st.divider()
st.caption("Prototype note: this is an evaluation aid, not a production customer-support system. Review responses for policy compliance before use.")
