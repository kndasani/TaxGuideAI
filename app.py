import streamlit as st
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="TaxGuide AI", 
    page_icon="🇮🇳", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

load_dotenv()

# --- 2. API KEY SETUP ---
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        st.error("🔑 API Key Missing.")
        st.stop()

genai.configure(api_key=api_key)

# --- 3. HELPER: RETRY LOGIC ---
def send_message_with_retry(chat_session, prompt, retries=3):
    for i in range(retries):
        try:
            return chat_session.send_message(prompt)
        except Exception as e:
            if "429" in str(e):
                time.sleep(2 ** (i + 1))
                continue
            else:
                raise e
    raise Exception("⚠️ AI Server busy. Please wait a moment.")

# --- 4. CALCULATOR & ITR ENGINE ---
def calculate_tax_logic(age, salary, business_income, rent_paid, inv_80c, med_80d):
    std_deduction_new = 75000 
    std_deduction_old = 50000
    
    # 1. Determine ITR Form
    itr_form = "ITR-1 (Sahaj)"
    if business_income > 0:
        itr_form = "ITR-4 (Sugam)" # Presumptive Business
    elif salary > 5000000:
        itr_form = "ITR-2" # High Income Salary
    
    # 2. Math Logic
    taxable_business = business_income * 0.50
    basic = salary * 0.50
    hra = max(0, rent_paid * 12 - (0.10 * basic))
    
    gross_old = (salary - std_deduction_old - hra) + taxable_business
    taxable_old = max(0, gross_old - min(inv_80c, 150000) - med_80d)
    taxable_new = max(0, (salary - std_deduction_new) + taxable_business)

    tax_new, tax_old = compute_slabs(taxable_new, taxable_old, age)
    return tax_new, tax_old, itr_form

def compute_slabs(inc_new, inc_old, age):
    # New Regime (FY 25-26)
    tax_new = 0
    t = inc_new
    if t > 2400000: tax_new += (t - 2400000) * 0.30; t = 2400000
    if t > 2000000: tax_new += (t - 2000000) * 0.25; t = 2000000
    if t > 1600000: tax_new += (t - 1600000) * 0.20; t = 1600000
    if t > 1200000: tax_new += (t - 1200000) * 0.15; t = 1200000
    if t > 800000:  tax_new += (t - 800000)  * 0.10; t = 800000
    if t > 400000:  tax_new += (t - 400000)  * 0.05
    if inc_new <= 1200000: tax_new = 0 

    # Old Regime
    limit = 500000 if age >= 80 else (300000 if age >= 60 else 250000)
    tax_old = 0
    t = inc_old
    if t > 1000000: tax_old += (t - 1000000) * 0.30; t = 1000000
    if t > 500000:  tax_old += (t - 500000)  * 0.20; t = 500000
    if t > limit:   tax_old += (t - limit)   * 0.05
    if inc_old <= 500000: tax_old = 0 

    return int(tax_new * 1.04), int(tax_old * 1.04)

# --- 5. LOAD KNOWLEDGE ---
@st.cache_resource
def load_knowledge():
    library = []
    files = ["salary_rules.pdf", "freelancer_rules.pdf", "capital_gains.pdf"]
    for f_name in files:
        if os.path.exists(f_name):
            try:
                f = genai.upload_file(path=f_name, display_name=f_name)
                while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
                library.append(f)
            except: pass
    return library

pdf_library = load_knowledge()

# --- 6. THE EDUCATOR BRAIN ---
sys_instruction = """
You are "TaxGuide AI", a patient and helpful Indian Tax Expert.
**Core Directive:** Do not just ask for data. *Educate* the user on what the data means.

**PHASE 1: PERSONA DISCOVERY**
- Introduce yourself warmly.
- Ask: "To give you the best advice, I need to know your income source. Do you earn a Salary, work as a Freelancer/Business owner, or both?"

**PHASE 2: GATHERING & EDUCATING**
- Ask questions ONE BY ONE.
- **Explain the 'Why':**
  - When asking for Age: "I need your age to check if you qualify for Senior Citizen benefits (higher exemption limits)."
  - When asking for Rent: "Do you live in a rented house? If yes, we can claim HRA exemption to lower your tax."
  - When asking for Investments: "Do you invest in PF, PPF, ELSS Mutual Funds, or Life Insurance? These fall under **Section 80C** and can save you tax on up to ₹1.5 Lakhs."
  - When asking for Medical: "Do you pay health insurance premiums? This is covered under **Section 80D**."

**PHASE 3: USE YOUR KNOWLEDGE BASE**
- If the user asks specific questions (e.g., "What is Section 44ADA?"), search the PDF files to provide an accurate answer.

**PHASE 4: EXECUTION**
- Once you have the data, output strictly:
  `CALCULATE(age=..., salary=..., business=..., rent=..., inv80c=..., med80d=...)`
"""

# --- 7. HEADER & DISCLAIMER ---
col1, col2 = st.columns([5, 1])
with col1:
    st.markdown("### 🇮🇳 TaxGuide AI")
with col2:
    if st.button("🔄", help="Reset Chat"):
        st.session_state.chat_session = None
        st.rerun()

st.warning("⚠️ **Disclaimer:** I am an AI Assistant. Tax laws are complex. Please verify these figures with a Chartered Accountant (CA) before filing.", icon="⚠️")
st.divider()

# --- 8. CHAT LOGIC ---
if "chat_session" not in st.session_state:
    history = []
    if pdf_library:
        history.append({"role": "user", "parts": pdf_library + ["Here is your tax library."]})
        history.append({"role": "model", "parts": ["I have studied the library."]})
    
    model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction)
    st.session_state.chat_session = model.start_chat(history=history)

# --- 9. WELCOME HINTS ---
if len(st.session_state.chat_session.history) <= 2:
    st.markdown("#### 👋 Hello! Let's plan your taxes.")
    st.info("I can explain tax rules and calculate your liability.\n\n👇 **Start by telling me:**\n*\"I work at a startup...\"* or *\"I am a freelance designer...\"*")

# --- 10. DISPLAY CHAT ---
start_idx = 2 if pdf_library else 0
for msg in st.session_state.chat_session.history[start_idx:]:
    role = "user" if msg.role == "user" else "assistant"
    avatar = "👤" if role == "user" else "🤖"
    with st.chat_message(role, avatar=avatar):
        st.markdown(msg.parts[0].text)

# --- 11. INPUT HANDLING ---
if prompt := st.chat_input("Type your answer..."):
    st.chat_message("user", avatar="👤").markdown(prompt)
    
    with st.spinner("Analyzing..."):
        try:
            response = send_message_with_retry(st.session_state.chat_session, prompt)
            text = response.text
            
            if "CALCULATE(" in text:
                try:
                    params = text.split("CALCULATE(")[1].split(")")[0]
                    data = {"age":30, "salary":0, "business":0, "rent":0, "inv80c":0, "med80d":0}
                    
                    for part in params.split(","):
                        if "=" in part:
                            key, val = part.split("=")
                            val_clean = ''.join(filter(str.isdigit, val.strip()))
                            if val_clean:
                                data[key.strip()] = int(val_clean)
                    
                    tn, to, itr = calculate_tax_logic(
                        data['age'], data['salary'], data['business'], 
                        data['rent'], data['inv80c'], data['med80d']
                    )
                    
                    savings = abs(tn - to)
                    winner = "New Regime" if tn < to else "Old Regime"
                    
                    st.chat_message("assistant", avatar="🤖").markdown(f"""
                    ### 🧾 Comprehensive Tax Report
                    
                    | Category | Details |
                    | :--- | :--- |
                    | **Recommended Regime** | **{winner}** |
                    | **Tax Payable** | **₹{min(tn, to):,}** |
                    | **Annual Savings** | ₹{savings:,} |
                    | **Recommended Form** | `{itr}` |
                    
                    ---
                    **Breakdown:**
                    * **New Regime Tax:** ₹{tn:,}
                    * **Old Regime Tax:** ₹{to:,}
                    """)
                    
                    st.session_state.chat_session.history.append({
                        "role": "model",
                        "parts": [f"Result shown: New={tn}, Old={to}, ITR={itr}"]
                    })

                except Exception as e:
                    st.error(f"Calculation Error: {e}")
            else:
                st.chat_message("assistant", avatar="🤖").markdown(text)
                
        except Exception as e:
            st.error(f"Error: {e}")