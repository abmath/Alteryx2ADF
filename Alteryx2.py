import streamlit as st
import time
import socket
import io
from openai import OpenAI
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

socket.setdefaulttimeout(30)

st.set_page_config(page_title="Alteryx to ADF Translator", layout="wide")
st.title("Alteryx Workflow to Azure Data Factory Instructions")

# api key input (yes, still ugly)
api_key = st.text_input("Enter OpenAI API Key", type="password")

client = None
if api_key != "":
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        st.error("Could not create OpenAI client")
        st.write(e)

# session state init
if "workflow_text" not in st.session_state:
    st.session_state.workflow_text = ""

if "workflow_name" not in st.session_state:
    st.session_state.workflow_name = "alteryx_workflow"

if "gpt_output" not in st.session_state:
    st.session_state.gpt_output = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def call_gpt(messages, temperature=0.2):
    tries = 0
    while tries < 3:
        try:
            return client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=messages,
                temperature=temperature,
                timeout=30
            )
        except Exception as e:
            tries += 1
            time.sleep(2)
            last_error = e
    raise last_error


uploaded_file = st.file_uploader(
    "Upload Alteryx Workflow (.yxmd)",
    type=["yxmd"]
)

if uploaded_file is not None:
    try:
        raw = uploaded_file.read()
        st.session_state.workflow_text = raw.decode("utf-8", errors="ignore")
        st.session_state.workflow_name = uploaded_file.name.replace(".yxmd", "")
        st.success("Workflow uploaded successfully")
    except Exception as e:
        st.error("Failed to read workflow")
        st.write(e)


if st.button("Generate ADF Step-by-Step Instructions") and st.session_state.gpt_output == "":

    if client is None:
        st.warning("Enter OpenAI API key first")

    elif st.session_state.workflow_text == "":
        st.warning("Upload an Alteryx workflow first")

    else:
        with st.spinner("Generating instructions..."):

            prompt = f"""
You are a senior Azure Data Factory engineer.

Convert the following Alteryx YXMD workflow into
VERY DETAILED, step by step instructions so that
a data engineer can rebuild it in Azure Data Factory
using GUI based Mapping Data Flows.

Rules:
- Do NOT write code
- Explain joins, filters, unions, and aggregations
- Mention Azure Data Factory UI elements explicitly

Alteryx Workflow:
{st.session_state.workflow_text}
"""

            try:
                response = call_gpt(
                    messages=[
                        {
                            "role": "system",
                            "content": "You translate Alteryx workflows into Azure Data Factory GUI instructions."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )

                st.session_state.gpt_output = response.choices[0].message.content

            except Exception as e:
                st.error("OpenAI call failed")
                st.write(e)


if st.session_state.gpt_output != "":
    st.subheader("Generated Azure Data Factory Instructions")
    st.text_area(
        "ADF Instructions",
        st.session_state.gpt_output,
        height=400
    )

    # ---- PDF GENERATION ----
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer)
    styles = getSampleStyleSheet()
    story = []

    for line in st.session_state.gpt_output.split("\n"):
        story.append(Paragraph(line.replace("&", "&amp;"), styles["Normal"]))

    doc.build(story)
    pdf_buffer.seek(0)

    pdf_filename = f"{st.session_state.workflow_name}_ADF_Instructions.pdf"

    st.download_button(
        label="Download Instructions as PDF",
        data=pdf_buffer,
        file_name=pdf_filename,
        mime="application/pdf"
    )


st.markdown("---")
st.subheader("Ask Questions About the Workflow")

question = st.text_input("Ask a question")

if st.button("Ask"):

    if client is None:
        st.warning("Enter OpenAI API key first")

    elif question == "":
        st.warning("Type a question")

    else:
        st.session_state.chat_history.append(
            {"role": "user", "content": question}
        )

        chat_prompt = f"""
Original Alteryx workflow:
{st.session_state.workflow_text}

Generated ADF instructions:
{st.session_state.gpt_output}

Answer the following question clearly and practically:
{question}
"""

        try:
            response = call_gpt(
                messages=[
                    {
                        "role": "system",
                        "content": "You help data engineers understand Alteryx workflows."
                    },
                    {
                        "role": "user",
                        "content": chat_prompt
                    }
                ],
                temperature=0.3
            )

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": response.choices[0].message.content
                }
            )

        except Exception as e:
            st.error("Chat failed")
            st.write(e)


for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f"**User:** {msg['content']}")
    else:
        st.markdown(f"**Assistant:** {msg['content']}")
