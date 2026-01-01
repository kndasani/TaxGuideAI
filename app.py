import streamlit as st
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

# --- CONFIGURATION & SETUP ---
load_dotenv() 
st.set_page_config(page_title="TaxGuide AI", page_icon="🇮🇳", layout="wide")

# Safe API Key Loading
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except FileNotFoundError:
        st.error("🔑 API Key Missing! Please add 'GEMINI_API_KEY' to your .env file or Streamlit Secrets.")
        st.stop()

genai.configure(api_key=api_key)

# --- 1. THE CALCULATOR ENGINES ---
def calculate_salary_tax(salary, rent_paid, inv_80c, med_80d):
    """Engine for Salaried Employees"""
    std_deduction_new = 75000  # FY 25-26
    std_deduction_old = 50000
    
    basic = salary * 0.50
    hra = max(0, rent_paid * 12 - (0.10 * basic))
    
    inc_old = salary - std_deduction_old - min(inv_80c, 150000) - med_80d - hra
    inc_new = salary - std_deduction_new 
    
    return compute_tax_slabs(inc_new, inc_old)

def calculate_freelance_tax(gross_receipts, expenses_claimed, inv_80c, med_80d):
    """Engine for Freelancers (Section 44ADA)"""
    presumptive_income = gross_receipts * 0.50
    inc_old = presumptive_income - min(inv_80c, 150000) - med_80d
    inc_new = presumptive_income 
    return compute_tax_slabs(inc_new, inc_old)

def compute_tax_slabs(inc_new, inc_old):
    """Shared Logic for Tax Slabs FY 2025-26"""
    # New Regime (FY 25-26 Updated)
    tax_new = 0
    temp = inc_new
    if temp > 2400000: tax_new += (temp - 2400000) * 0.30; temp = 2400000
    if temp > 2000000: tax_new += (temp - 2000000) * 0.25; temp = 2000000
    if temp > 1600000: tax_new += (temp - 1600000) * 0.20; temp = 1600000
    if temp > 1200000: tax_new += (temp - 1200000) * 0.15; temp = 1200000
    if temp > 800000:  tax_new += (temp - 800000)  * 0.10; temp = 800000
    if temp > 400000:  tax_new += (temp - 400000)  * 0.05
    if inc_new <= 1200000: tax_new = 0 # Rebate

    # Old Regime (Unchanged)
    tax_old = 0
    temp = inc_old
    if temp > 1000000: tax_old += (temp - 1000000) * 0.30; temp = 1000000
    if temp > 500000:  tax_old += (temp - 500000)  * 0.20; temp = 500000
    if temp > 250000:  tax_old += (temp - 250000)  * 0.05
    if inc_old <= 500000: tax_old = 0 # Rebate
        
    return int(tax_new * 1.04), int(tax_old * 1.04)

# --- 2. LOAD PDF LIBRARY ---
@st.cache_resource
def load_rag_data():
    library = []
    # Map filenames to nice names
    target_files = {
        "salary_rules.pdf": "Salary Rules",
        "freelancer_rules.pdf": "Freelancer Rules",
        "capital_gains.pdf": "Capital Gains Rules"
    }
    for filename, display_name in target_files.items():
        if os.path.exists(filename):
            try:
                f = genai.upload_file(path=filename, display_name=display_name)
                while f.state.name == "PROCESSING":
                    time.sleep(1)
                    f = genai.get_file(f.name)
                library.append(f)
            except Exception:
                continue 
    return library

pdf_library = load_rag_data()

# --- 3. SIDEBAR (PROFILE & DISCLAIMER) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2534/2534204.png", width=50)
    st.title("TaxGuide AI")
    st.markdown("Your AI Tax Assistant for FY 2025-26")
    
    st.markdown("---")
    st.subheader("👤 Select Profile")
    user_type = st.radio(
        "I am a:",
        ["Salaried Employee", "Freelancer / Doctor", "Investor / Trader"]
    )
    
    st.markdown("---")
    st.warning("⚠️ **Disclaimer:**\nI am an AI, not a Chartered Accountant. Tax laws are complex. Please verify calculations with a professional before filing.")

# --- 4. BRAIN INSTRUCTIONS ---
if user_type == "Salaried Employee":
    sys_instruction = """
    Role: Expert Tax Assistant for Salaried Employees (FY 2025-26).
    Knowledge: Use 'Salary Rules' PDF.
    Goal: Gather Salary, Rent, 80C, 80D.
    Output: `CALCULATE_SALARY(salary=..., rent=..., inv80c=..., med80d=...)`
    """
elif user_type == "Freelancer / Doctor":
    sys_instruction = """
    Role: Expert Tax Assistant for Freelancers (Section 44ADA).
    Knowledge: Use 'Freelancer Rules' PDF.
    Goal: Gather Gross Receipts, 80C, 80D.
    Output: `CALCULATE_FREELANCE(receipts=..., inv80c=..., med80d=...)`
    """
else:
    sys_instruction = "Role: Expert Tax Advisor for Investors. Use 'Capital Gains Rules' PDF. Explain rules, do NOT calculate tax."

# --- 5. CHAT INTERFACE ---
if "chat_session" not in st.session_state or st.session_state.get("last_persona") != user_type:
    history = []
    if pdf_library:
        history.append({"role": "user", "parts": pdf_library + ["Use these tax rules."]})
        history.append({"role": "model", "parts": ["Understood. I have access to the library."]})
    
    # FIX: Using 'gemini-2.0-flash' which is available in your list
    try:
        model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction)
    except:
        model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction)
        
    st.session_state.chat_session = model.start_chat(history=history)
    st.session_state.last_persona = user_type

# --- 6. WELCOME SCREEN ---
if len(st.session_state.chat_session.history) <= 2:
    st.markdown(f"## 👋 Hello! I'm your {user_type} Assistant.")
    st.markdown("I can help you plan taxes, choose regimes, and understand rules.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("💰 **Ask me to calculate your tax**")
    with col2:
        st.info("👇 **Type below to start!**\n*Example: My salary is 18 Lakhs...*")

# --- 7. DISPLAY HISTORY ---
start_idx = 2 if pdf_library else 0
for msg in st.session_state.chat_session.history[start_idx:]:
    role = "user" if msg.role == "user" else "assistant"
    with st.chat_message(role):
        st.markdown(msg.parts[0].text)

# --- 8. HANDLE INPUT ---
if prompt := st.chat_input("Ask about tax savings, HRA, or calculations..."):
    st.chat_message("user").markdown(prompt)
    
    with st.spinner("Analyzing Tax Rules..."):
        try:
            response = st.session_state.chat_session.send_message(prompt)
            text = response.text
            
            # Catch Calculator Triggers
            if "CALCULATE_" in text:
                try:
                    if "CALCULATE_SALARY" in text:
                        params = text.split("CALCULATE_SALARY(")[1].split(")")[0]
                        s = int(params.split("salary=")[1].split(",")[0])
                        r = int(params.split("rent=")[1].split(",")[0])
                        i = int(params.split("inv80c=")[1].split(",")[0])
                        m = int(params.split("med80d=")[1].split(")")[0])
                        tn, to = calculate_salary_tax(s, r, i, m)
                        
                    elif "CALCULATE_FREELANCE" in text:
                        params = text.split("CALCULATE_FREELANCE(")[1].split(")")[0]
                        g = int(params.split("receipts=")[1].split(",")[0])
                        i = int(params.split("inv80c=")[1].split(",")[0])
                        m = int(params.split("med80d=")[1].split(")")[0])
                        tn, to = calculate_freelance_tax(g, 0, i, m)

                    savings = abs(tn - to)
                    winner = "New Regime" if tn < to else "Old Regime"
                    
                    st.chat_message("assistant").markdown(f"""
                    ### 📊 Tax Analysis Complete
                    | Regime | Tax Payable |
                    | :--- | :--- |
                    | **New Regime** | **₹{tn:,}** |
                    | **Old Regime** | **₹{to:,}** |
                    
                    🎉 **Recommendation:** Choose **{winner}**.
                    You will save **₹{savings:,}** per year!
                    """)
                except:
                    st.chat_message("assistant").markdown(text)
            else:
                st.chat_message("assistant").markdown(text)
                
        except Exception as e:
            st.error(f"⚠️ Error: {e}")