import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import extra_streamlit_components as stx
from datetime import datetime, timedelta
import time

# --- 1. SETTINGS & INITIALIZATION ---
st.set_page_config(page_title="The Compass", page_icon="⚓", layout="centered")

@st.cache_resource
def init_connections():
    # Clean URL and Key
    url = st.secrets["SUPABASE_URL"].strip().rstrip("/")
    key = st.secrets["SUPABASE_KEY"].strip()
    supabase_client = create_client(url, key)
    # Init Gemini
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    return supabase_client

try:
    supabase = init_connections()
except Exception as e:
    st.error("Connection to Support Station failed. Check your Internet/Settings.")
    st.stop()

cookie_manager = stx.CookieManager()

# --- 2. AUTHENTICATION HELPERS ---
def sign_up(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        return res.user
    except Exception as e:
        st.error(f"Signup failed: {e}")
        return None

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res.user
    except Exception as e:
        st.error("Login failed. Check your details or ensure account is created.")
        return None

# --- 3. SESSION MANAGEMENT ---
# Get cookie once at start
if "user_id" not in st.session_state:
    val = cookie_manager.get(cookie="seafarer_session_id")
    st.session_state.user_id = val

# --- 4. LOGIN / SIGNUP UI ---
if not st.session_state.user_id:
    st.title("⚓ The Compass")
    st.subheader("Maritime Mental Resilience Assistant")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        l_email = st.text_input("Email", key="l_email")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login", use_container_width=True):
            user = login(l_email, l_pass)
            if user:
                cookie_manager.set("seafarer_session_id", user.id, expires_at=datetime.now() + timedelta(days=90))
                st.session_state.user_id = user.id
                st.success("Authenticated. Redirecting...")
                time.sleep(1)
                st.rerun()

    with tab2:
        s_email = st.text_input("Email", key="s_email")
        s_pass = st.text_input("Password", type="password", key="s_pass")
        st.caption("Password must be 6+ characters.")
        if st.button("Create Account", use_container_width=True):
            if len(s_pass) < 6:
                st.error("Password too short.")
            else:
                user = sign_up(s_email, s_pass)
                if user:
                    st.success("Account created! Please switch to the Login tab.")

# --- 5. CHAT INTERFACE (LOGGED IN) ---
else:
    u_id = st.session_state.user_id
    
    # Sidebar with Logout and Safety Resources
    with st.sidebar:
        st.title("⚓ Ship's Office")
        if st.button("Logout / Clear Session"):
            cookie_manager.delete("seafarer_session_id")
            st.session_state.user_id = None
            st.rerun()
        
        st.divider()
        st.warning("🆘 EMERGENCY RESOURCES")
        st.write("If you are in physical danger or need immediate human help:")
        st.write("- **ISWAN:** +44 7309 561815 (WhatsApp)")
        st.write("- **SeafarerHelp:** 24/7 Hotline available")

    st.title("⚓ The Compass")

    # Initialize History
    if "messages" not in st.session_state:
        try:
            res = supabase.table("chat_history").select("role, content").eq("user_id", u_id).order("created_at").execute()
            st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in res.data]
        except:
            st.session_state.messages = []

    # Display History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if prompt := st.chat_input("How are you feeling on watch today?"):
        st.chat_message("user").markdown(prompt)
        
        # 1. Save User Message to DB (Try/Except to prevent red screen)
        try:
            supabase.table("chat_history").insert({
                "user_id": u_id,
                "role": "user",
                "content": prompt
            }).execute()
        except Exception as e:
            st.error("Warning: Message not saved to history, but AI will still answer.")

        # 2. Get AI Response
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Prepare memory for Gemini
        history_for_gemini = []
        for m in st.session_state.messages:
            role = "user" if m["role"] == "user" else "model"
            history_for_gemini.append({"role": role, "parts": [m["content"]]})
        
        chat = model.start_chat(history=history_for_gemini)
        
        with st.chat_message("assistant"):
            try:
                # Optimized System Prompt
                context = (
                    "You are 'The Compass', a mental resilience bot for seafarers. "
                    "Provide short, actionable mental or physical exercises. "
                    "If a user mentions not eating, self-harm, or severe physical symptoms, "
                    "advise them to contact the Medical Officer or ISWAN immediately."
                )
                response = chat.send_message(f"{context}\n\nUser: {prompt}")
                ai_text = response.text
                st.markdown(ai_text)
                
                # 3. Save AI Message to DB
                try:
                    supabase.table("chat_history").insert({
                        "user_id": u_id,
                        "role": "assistant",
                        "content": ai_text
                    }).execute()
                except:
                    pass
                
                # Update Session State
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                
            except Exception as e:
                st.error("The AI is currently off-watch. Try again in a minute.")
