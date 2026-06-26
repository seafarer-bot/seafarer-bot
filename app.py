import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import extra_streamlit_components as stx
from datetime import datetime, timedelta

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="The Compass", page_icon="⚓", layout="centered")

# Initialize Supabase
@st.cache_resource
def init_supabase():
    # Ensure URL has no trailing slashes or extra paths
    url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    key = st.secrets["SUPABASE_KEY"].strip()
    return create_client(url, key)

supabase = init_supabase()

# Initialize Gemini
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Initialize Cookie Manager
cookie_manager = stx.CookieManager()

# --- 2. AUTHENTICATION FUNCTIONS ---
def sign_up_user(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        return res
    except Exception as e:
        st.error(f"Signup Error: {e}")
        return None

def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res
    except Exception as e:
        st.error("Login failed. Check your email/password or confirm if account exists.")
        return None

# --- 3. SESSION & COOKIE LOGIC ---
# We check both the cookie and the session state to ensure instant login
if "user_id" not in st.session_state:
    st.session_state.user_id = cookie_manager.get(cookie="seafarer_session_id")

# --- 4. UI: LOGIN/SIGNUP OR CHAT ---
if not st.session_state.user_id:
    st.title("⚓ The Compass")
    st.info("Maritime Mental Resilience Assistant")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        l_email = st.text_input("Email", key="l_email")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login", use_container_width=True):
            res = login_user(l_email, l_pass)
            if res and res.user:
                # Save to Cookie (90 days)
                cookie_manager.set("seafarer_session_id", res.user.id, expires_at=datetime.now() + timedelta(days=90))
                # Save to Session State (Instant)
                st.session_state.user_id = res.user.id
                st.success("Login Successful!")
                st.rerun()

    with tab2:
        st.write("Create an account to save your progress.")
        s_email = st.text_input("Email", key="s_email")
        s_pass = st.text_input("Password", type="password", key="s_pass")
        st.caption("Password must be at least 6 characters.")
        if st.button("Create Account", use_container_width=True):
            if len(s_pass) < 6:
                st.error("Password too short.")
            else:
                res = sign_up_user(s_email, s_pass)
                if res:
                    st.success("Account created! You can now switch to the Login tab.")

else:
    # --- 5. LOGGED IN: THE CHAT INTERFACE ---
    current_user_id = st.session_state.user_id
    
    with st.sidebar:
        st.title("⚓ Navigation")
        st.write(f"Logged in as Seafarer")
        if st.button("Logout"):
            cookie_manager.delete("seafarer_session_id")
            st.session_state.user_id = None
            st.rerun()

    st.title("⚓ The Compass")
    st.write("How are you handling things on watch today?")

    # Load History from Database
    if "messages" not in st.session_state:
        try:
            res = supabase.table("chat_history").select("role, content").eq("user_id", current_user_id).order("created_at").execute()
            st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in res.data]
        except:
            st.session_state.messages = []

    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("I'm feeling stressed because..."):
        # Display User message
        st.chat_message("user").markdown(prompt)
        
        # Save User message to DB
        # Save User message to DB
supabase.table("chat_history").insert({
    "user_id": current_user_id,
    "role": "user",
    "content": prompt
}).execute()

        # Generate AI response
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Format history for Gemini (roles must be 'user' or 'model')
        history_for_ai = []
        for m in st.session_state.messages:
            history_for_ai.append({
                "role": "user" if m["role"] == "user" else "model",
                "parts": [m["content"]]
            })
        
        chat = model.start_chat(history=history_for_ai)
        
        with st.chat_message("assistant"):
            try:
                # System instructions integrated into the call
                full_prompt = f"Context: You are a maritime mental resilience coach. A seafarer is talking to you. Help them with actionable exercises. User input: {prompt}"
                response = chat.send_message(full_prompt)
                ai_text = response.text
                st.markdown(ai_text)
                
                # Save AI message to DB
                supabase.table("chat_history").insert({
                    "user_id": current_user_id,
                    "role": "assistant",
                    "content": ai_text
                }).execute()
                
                # Update Session State
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                
            except Exception as e:
                st.error("The communication link is patchy. Try again in a moment.")
