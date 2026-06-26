import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import extra_streamlit_components as stx
from datetime import datetime, timedelta

# --- INITIALIZATION ---
st.set_page_config(page_title="The Compass", page_icon="⚓")
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Setup Cookie Manager (The "Remember Me" engine)
cookie_manager = stx.CookieManager()

def get_session():
    return cookie_manager.get(cookie="seafarer_session_id")

# --- AUTHENTICATION FUNCTIONS ---
def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        return res
    except Exception as e:
        st.error(f"Signup failed: {e}")

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res
    except Exception as e:
        st.error(f"Login failed: Check your email/password")

# --- APP LOGIC ---
session_id = get_session()

# If not logged in, show Login/Signup Page
if not session_id:
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to your Station")
        l_email = st.text_input("Email", key="l_email")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login"):
            res = login(l_email, l_pass)
            if res:
                # Set cookie for 90 days
                cookie_manager.set("seafarer_session_id", res.user.id, expires_at=datetime.now() + timedelta(days=90))
                st.success("Logged in! Please refresh or click again.")
                st.rerun()

    with tab2:
        st.subheader("Create New Account")
        s_email = st.text_input("Email", key="s_email")
        s_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up"):
            res = sign_up(s_email, s_pass)
            if res:
                st.success("Account created! You can now log in.")

# If logged in, show the Chat
else:
    user_id = session_id
    st.sidebar.button("Logout", on_click=lambda: cookie_manager.delete("seafarer_session_id"))
    
    st.title("⚓ The Compass")
    
    # 1. Load History from Supabase
    if "messages" not in st.session_state:
        res = supabase.table("chat_history").select("*").eq("user_id", user_id).order("created_at").execute()
        st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in res.data]

    # 2. Display Chat
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 3. Chat Input
    if prompt := st.chat_input("Describe your situation..."):
        st.chat_message("user").markdown(prompt)
        
        # Save User Message
        supabase.table("chat_history").insert({"user_id": user_id, "role": "user", "content": prompt}).execute()

        # Generate AI Response
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Simple history formatting
        history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in st.session_state.messages]
        chat = model.start_chat(history=history)
        
        try:
            response = chat.send_message(prompt)
            full_response = response.text
            
            # Save AI Response
            supabase.table("chat_history").insert({"user_id": user_id, "role": "assistant", "content": full_response}).execute()

            with st.chat_message("assistant"):
                st.markdown(full_response)
            
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        except Exception as e:
            st.error("Connection lost. Please try again.")
