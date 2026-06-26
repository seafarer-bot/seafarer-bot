import streamlit as st
from supabase import create_client
from google import genai
import extra_streamlit_components as stx
from datetime import datetime, timedelta
import time

# ---------------- PAGE CONFIG ---------------- #

st.set_page_config(
    page_title="The Compass",
    page_icon="⚓",
    layout="centered"
)

# ---------------- CONNECTIONS ---------------- #

@st.cache_resource
def init():
    supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    client = genai.Client(
        api_key=st.secrets["GOOGLE_API_KEY"]
    )

    return supabase, client


supabase, gemini = init()

cookie_manager = stx.CookieManager()

# ---------------- SESSION ---------------- #

if "user_id" not in st.session_state:
    st.session_state.user_id = cookie_manager.get(
        cookie="compass_user"
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------- AUTH FUNCTIONS ---------------- #

def signup(email, password):
    try:
        res = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        return True

    except Exception as e:
        st.error(str(e))
        return False


def login(email, password):

    try:

        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        cookie_manager.set(
            "compass_user",
            res.user.id,
            expires_at=datetime.now() + timedelta(days=90)
        )

        st.session_state.user_id = res.user.id

        return True

    except Exception as e:

        st.error(str(e))

        return False


def logout():

    cookie_manager.delete("compass_user")

    st.session_state.user_id = None

    st.session_state.messages = []

    st.rerun()

# ---------------- LOGIN SCREEN ---------------- #

if st.session_state.user_id is None:

    st.title("⚓ The Compass")

    st.subheader("Mental Wellbeing Assistant for Seafarers")

    login_tab, signup_tab = st.tabs([
        "Login",
        "Create Account"
    ])

    with login_tab:

        email = st.text_input(
            "Email",
            key="login_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_pass"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            if login(email, password):

                st.success("Welcome aboard!")

                time.sleep(1)

                st.rerun()

    with signup_tab:

        email = st.text_input(
            "Email",
            key="signup_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="signup_pass"
        )

        if st.button(
            "Create Account",
            use_container_width=True
        ):

            if len(password) < 6:

                st.error("Password must be at least 6 characters.")

            else:

                if signup(email, password):

                    st.success(
                        "Account created successfully."
                    )

                    st.info(
                        "Go to Login and sign in."
                    )

    st.stop()

# ---------------- SIDEBAR ---------------- #

with st.sidebar:

    st.title("⚓ The Compass")

    st.write("Welcome back!")

    if st.button("Logout"):

        logout()

    st.divider()

    st.warning("Emergency Help")

    st.write("""
If you feel unsafe or are considering self-harm,
please contact:

• Master / Captain

• Medical Officer

• ISWAN SeafarerHelp
https://www.seafarerhelp.org

Available 24/7
""")

st.title("⚓ The Compass")

st.caption(
    "Tell me what is happening onboard."
)
# ---------------- LOAD CHAT HISTORY ---------------- #

try:

    history = (
        supabase.table("chat_history")
        .select("*")
        .eq("user_id", st.session_state.user_id)
        .order("created_at")
        .execute()
    )

    if len(st.session_state.messages) == 0:

        for row in history.data:

            st.session_state.messages.append(
                {
                    "role": row["role"],
                    "content": row["content"]
                }
            )

except Exception as e:

    st.error("Unable to load previous conversations.")

# ---------------- DISPLAY CHAT ---------------- #

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])

# ---------------- CHAT INPUT ---------------- #

prompt = st.chat_input(
    "Describe what you're experiencing..."
)

if prompt:

    # ---------- USER MESSAGE ---------- #

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)

    try:

        supabase.table("chat_history").insert(
            {
                "user_id": st.session_state.user_id,
                "role": "user",
                "content": prompt
            }
        ).execute()

    except Exception as e:

        st.warning("Unable to save your message.")

    # ---------- SYSTEM PROMPT ---------- #

    system_prompt = """
You are The Compass.

You are a wellbeing assistant designed ONLY for seafarers.

You do NOT diagnose mental illness.

You do NOT prescribe medication.

Always respond in this format.

## Understanding Your Situation

Briefly explain what the user may be experiencing.

## Things You Can Practice Right Now

Give 5 practical actions.

## Breathing Exercise

Explain one breathing exercise.

## Grounding Exercise

Explain one grounding exercise.

## Physical Activity

Suggest a simple onboard activity.

## Reflection

Provide one journal question.

## Reminder

Encourage speaking to trusted crew or welfare services if distress continues.

If the user mentions:

suicide
self harm
want to die
kill myself

Respond calmly and encourage immediate contact with the Captain, Medical Officer, ISWAN SeafarerHelp or emergency services.
"""

    # ---------- BUILD HISTORY ---------- #

    history = []

    for m in st.session_state.messages[:-1]:

        role = "model"

        if m["role"] == "user":

            role = "user"

        history.append(
            {
                "role": role,
                "parts": [
                    {
                        "text": m["content"]
                    }
                ]
            }
        )

    # ---------- GEMINI ---------- #

    with st.chat_message("assistant"):

        try:

            response = gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    system_prompt,
                    prompt
                ]
            )

            ai_text = response.text

            st.markdown(ai_text)

        except Exception as e:

            st.exception(e)

            st.stop()

    # ---------- SAVE RESPONSE ---------- #

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": ai_text
        }
    )

    try:

        supabase.table("chat_history").insert(
            {
                "user_id": st.session_state.user_id,
                "role": "assistant",
                "content": ai_text
            }
        ).execute()

    except:

        pass

    st.rerun()
    
