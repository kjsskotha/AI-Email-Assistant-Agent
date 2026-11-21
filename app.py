
import streamlit as st
import sqlite3
import json
from datetime import datetime
from langchain_groq import ChatGroq

# ---------------- PAGE CONFIGURATION ----------------

st.set_page_config(
    page_title="AI Email Assistant",
    page_icon="📧",
    layout="wide"
)

# ---------------- DATABASE ----------------

DB_NAME = "drafts.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            body TEXT,
            action TEXT,
            date TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_draft(subject, body, action):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO drafts (subject, body, action, date)
        VALUES (?, ?, ?, ?)
    """, (
        subject,
        body,
        action,
        datetime.now().strftime("%d-%m-%Y %H:%M")
    ))

    conn.commit()
    conn.close()


def get_drafts():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, subject, body, action, date
        FROM drafts
        ORDER BY id DESC
    """)

    drafts = cursor.fetchall()
    conn.close()

    return drafts


init_db()

# ---------------- GROQ AI MODEL ----------------

def ask_ai(user_input, selected_action):

    if selected_action == "Auto Detect":
        text = user_input.lower()

        if any(word in text for word in [
            "categorize", "category", "classify"
        ]):
            action = "Categorize Email"

        elif any(word in text for word in [
            "reply", "respond", "response"
        ]):
            action = "Suggest Reply"

        else:
            action = "Generate Email"

    else:
        action = selected_action

    # Connect to Groq
    api_key = st.secrets.get("GROQ_API_KEY", "")

    if not api_key:
        raise ValueError(
            "Groq API key is missing. Add GROQ_API_KEY in Streamlit Secrets."
        )

    model = ChatGroq(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        temperature=0.3
    )

    # ---------------- PROMPTS ----------------

    if action == "Generate Email":

        prompt = f"""
        You are a professional email writing assistant.

        Create a clear, polite and professional email
        based on the user's request.

        Return ONLY valid JSON in this format:
        {{
            "subject": "Email subject",
            "body": "Complete email body"
        }}

        User request:
        {user_input}
        """

    elif action == "Suggest Reply":

        prompt = f"""
        You are a professional email assistant.

        Write a polite and suitable reply to the given email.

        Return ONLY valid JSON in this format:
        {{
            "subject": "Reply subject",
            "body": "Complete reply"
        }}

        Email:
        {user_input}
        """

    else:

        prompt = f"""
        You are an email classification assistant.

        Categorize the email into exactly one category:
        Work, Personal, or Urgent.

        Give a short reason for the category.

        Return ONLY valid JSON in this format:
        {{
            "category": "Work",
            "reason": "Reason for this category"
        }}

        Email:
        {user_input}
        """

    # ---------------- GET AI RESPONSE ----------------

    response = model.invoke(prompt)
    result = response.content

    if not isinstance(result, str):
        raise ValueError("The AI returned an invalid response.")

    # Extract JSON
    start = result.find("{")
    end = result.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError("The AI response was not valid JSON.")

    data = json.loads(result[start:end])

    # ---------------- VALIDATE RESULT ----------------

    if action == "Categorize Email":

        category = str(data.get("category", "")).strip()
        reason = str(data.get("reason", "")).strip()

        if category not in ["Work", "Personal", "Urgent"]:
            raise ValueError("Invalid category returned by AI.")

        if not reason:
            raise ValueError("The AI did not provide a reason.")

        return action, {
            "category": category,
            "reason": reason
        }

    else:

        subject = str(data.get("subject", "")).strip()
        body = str(data.get("body", "")).strip()

        if not subject or not body:
            raise ValueError("The AI returned an incomplete email.")

        return action, {
            "subject": subject,
            "body": body
        }


# ---------------- MAIN APPLICATION ----------------

st.title("📧 AI EMAIL ASSISTANT AGENT")

st.caption(
    "Your smart assistant for generating, replying to and categorizing emails."
)

st.divider()

# ---------------- DASHBOARD ----------------

drafts = get_drafts()

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Saved Drafts", len(drafts))

with col2:
    st.metric("AI Actions", "3")

with col3:
    st.metric("Storage", "SQLite")

st.divider()

# ---------------- EMAIL ASSISTANT ----------------

st.subheader("✉️ Email Assistant")

selected_action = st.selectbox(
    "Choose an action",
    [
        "Auto Detect",
        "Generate Email",
        "Suggest Reply",
        "Categorize Email"
    ]
)

user_input = st.text_area(
    "Enter your email request or paste an email",
    placeholder="Example: Write a professional email requesting leave for two days...",
    height=150
)

if st.button("✨ Generate Result", use_container_width=True):

    if not user_input.strip():

        st.warning("Please enter some text before generating.")

    else:

        try:

            with st.spinner("AI is processing your request..."):

                action, result = ask_ai(
                    user_input,
                    selected_action
                )

                st.session_state["action"] = action
                st.session_state["result"] = result

            st.success("Result generated successfully!")

        except Exception as e:

            st.error("Unable to generate a result.")

            st.caption(str(e))


# ---------------- DISPLAY RESULT ----------------

if "result" in st.session_state:

    action = st.session_state["action"]
    result = st.session_state["result"]

    st.divider()
    st.subheader("📄 Generated Result")

    if action == "Categorize Email":

        st.info("Email Category")

        st.markdown(f"### {result['category']}")

        st.write("**Reason:**")
        st.write(result["reason"])

    else:

        edited_subject = st.text_input(
            "Email Subject",
            value=result["subject"],
            key="edited_subject"
        )

        edited_body = st.text_area(
            "Email Body",
            value=result["body"],
            height=200,
            key="edited_body"
        )

        st.caption(
            "You can edit the generated email before saving it."
        )

        if st.button("💾 Save Draft", use_container_width=True):

            if edited_subject.strip() and edited_body.strip():

                save_draft(
                    edited_subject,
                    edited_body,
                    action
                )

                st.success("Draft saved successfully!")

            else:

                st.warning(
                    "Subject and body cannot be empty."
                )


# ---------------- SAVED DRAFT HISTORY ----------------

st.divider()
st.subheader("📂 Saved Draft History")

drafts = get_drafts()

if drafts:

    for draft in drafts:

        draft_id, subject, body, action, date = draft

        with st.expander(f"{subject} — {date}"):

            st.write("**Action:**", action)
            st.write("**Subject:**", subject)
            st.write("**Email Body:**")
            st.write(body)

else:

    st.info(
        "No saved drafts yet. Generate and save an email to see it here."
    )
