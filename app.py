import streamlit as st
import google.generativeai as genai
import os
import time
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="TaxGuide AI", page_icon="🇮🇳", layout="centered", initial_sidebar_state="collapsed")
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try: api_key = st.secrets["GEMINI_API_KEY"]
    except: st.error("🔑 API Key Missing."); st.stop()

genai.configure(api_key=api_key)

# --- 2. HELPER: RETRY LOGIC ---
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
    raise Exception("⚠️ Server busy. Please wait 1 minute.")

# --- 3. SMART KNOWLEDGE LOADER ---
@st.cache_resource
def get_pdf_file(filename):
    if os.path.exists(filename):
        try:
            f = genai.upload_file(path=filename, display_name=filename)
            while f.state.name == "PROCESSING": time.sleep(1); f = genai.get_file(f.name)
            return f
        except: return None
    return None

def inject_knowledge(persona_type):
    if persona_type == "SALARY": return get_pdf_file("salary_rules.pdf")
    elif persona_type == "BUSINESS": return get_pdf_file("freelancer_rules.pdf")
    elif persona_type == "CAPITAL_GAINS": return get_pdf_file("capital_gains.pdf")
    return None

# --- 4. CALCULATOR ENGINE ---
def calculate_tax_detailed(age, salary, business_income, rent_paid, inv_80c, med_80d):
    std_deduction_new = 75000; std_deduction_old = 50000
    
    # Income Logic
    taxable_business = business_income * 0.50
    basic = salary * 0.50
    hra_exemption = max(0, rent_paid * 12 - (0.10 * basic))
    
    gross = salary + taxable_business
    deductions_old = std_deduction_old + hra_exemption + min(inv_80c, 150000) + med_80d
    
    net_old = max(0, gross - deductions_old)
    net_new = max(0, gross - std_deduction_new)

    # Tax Math
    bd_new = compute_tax_breakdown(net_new, age, "new")
    bd_old = compute_tax_breakdown(net_old, age, "old")
    
    # Return everything needed for the Receipt
    return {
        "new": {"breakdown": bd_new, "net": net_new},
        "old": {"breakdown": bd_old, "net": net_old, 
                "deductions": {
                    "std": std_deduction_old,
                    "hra": hra_exemption,
                    "80c": min(inv_80c, 150000),
                    "80d": med_80d
                }
        }
    }

def compute_tax_breakdown(income, age, regime):
    tax = 0
    # 1. SLABS
    if regime == "new":
        t = income
        if t > 2400000: tax += (t-2400000)*0.30; t=2400000
        if t > 2000000: tax += (t-2000000)*0.25; t=2000000
        if t > 1600000: tax += (t-1600000)*0.20; t=1600000
        if t > 1200000: tax += (t-1200000)*0.15; t=1200000
        if t > 800000:  tax += (t-800000)*0.10;  t=800000
        if t > 400000:  tax += (t-400000)*0.05
        if income <= 1200000: tax = 0
    else:
        limit = 500000 if age >= 80 else (300000 if age >= 60 else 250000)
        t = income
        if t > 1000000: tax += (t-1000000)*0.30; t=1000000
        if t > 500000:  tax += (t-500000)*0.20;  t=500000
        if t > limit:   tax += (t-limit)*0.05
        if income <= 500000: tax = 0

    # 2. SURCHARGE & CESS
    surcharge = 0
    if income > 5000000:
        rate = 0.10 if income <= 10000000 else 0.15
        if income > 20000000: rate = 0.25
        if regime == "old" and income > 50000000: rate = 0.37
        surcharge = tax * rate

    cess = (tax + surcharge) * 0.04
    total = int(tax + surcharge + cess)
    
    return {"base": int(tax), "surcharge": int(surcharge), "cess": int(cess), "total": total}

# --- 5. THE EMPATHETIC BRAIN ---
sys_instruction = """
You are "TaxGuide AI", a friendly tax consultant. 
**CORE RULE: NEVER use Jargon.** Don't say "80C" or "80D" in questions. Use plain English.

**LOGIC FLOW:**

1. **START:** Ask: "How do you earn your living? (e.g., Salary, Business?)"

2. **DETECT & LOAD:**
   - User: "Salary" -> Output: `LOAD(SALARY)`
   - User: "Business" -> Output: `LOAD(BUSINESS)`

3. **THE INTERVIEW (Simple English Only):**
   - **Age:** "First, what is your age?"
   - **Income:** "What is your total annual income?"
   - **Housing:** "Do you live in a rented house? If yes, what is your monthly rent?" (Map internally to HRA).
   - **Investments:** "Do you have any savings like **PF, PPF, Life Insurance, or Children's Tuition Fees**?" (Map to 80C).
   - **Health:** "Do you pay for **Medical Insurance** for your family?" (Map to 80D).

4. **CALCULATE:**
   - Output: `CALCULATE(age=..., salary=..., business=..., rent=..., inv80c=..., med80d=...)`
"""

# --- 6. UI HEADER ---
col1, col2 = st.columns([5, 1])
with col1: st.markdown("### 🇮🇳 TaxGuide AI")
with col2: 
    if st.button("🔄", help="Reset"):
        st.session_state.clear()
        st.rerun()

# --- 7. FORK LOGIC ---
if "mode" not in st.session_state:
    st.session_state.mode = None
    st.session_state.chat_session = None
    st.session_state.loaded_persona = None

if st.session_state.mode is None:
    st.markdown("#### 👋 How can I help you today?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💰 Calculate My Tax", use_container_width=True):
            st.session_state.mode = "CALC"
            model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction)
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.chat_session.history.append({"role": "model", "parts": ["Hi! Let's calculate. Do you earn a Salary or run a Business?"]})
            st.rerun()
    with c2:
        if st.button("📚 Ask Tax Rules", use_container_width=True):
            st.session_state.mode = "RULES"
            model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction)
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.chat_session.history.append({"role": "model", "parts": ["I can explain rules. What topic?"]})
            st.rerun()

else:
    # History
    for msg in st.session_state.chat_session.history:
        text, role = "", ""
        if isinstance(msg, dict):
            role = msg.get("role"); parts = msg.get("parts", [])
            if parts and isinstance(parts[0], str): text = parts[0]
        else:
            role = msg.role; text = msg.parts[0].text
            
        if text and "LOAD" not in text and "Result:" not in text:
            role_name = "user" if role == "user" else "assistant"
            avatar = "👤" if role == "user" else "🤖"
            with st.chat_message(role_name, avatar=avatar):
                st.markdown(text)

    # Input
    if prompt := st.chat_input("Type here..."):
        st.chat_message("user", avatar="👤").markdown(prompt)
        
        with st.spinner("Thinking..."):
            try:
                response = send_message_with_retry(st.session_state.chat_session, prompt)
                text = response.text
                
                # LOAD LOGIC
                if "LOAD(" in text:
                    persona = text.split("LOAD(")[1].split(")")[0]
                    if st.session_state.loaded_persona != persona:
                        file_ref = inject_knowledge(persona)
                        if file_ref:
                            hist = st.session_state.chat_session.history[:-1]
                            hist.append({"role": "user", "parts": [file_ref, "Rules loaded."]})
                            hist.append({"role": "model", "parts": ["Understood."]})
                            model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction)
                            st.session_state.chat_session = model.start_chat(history=hist)
                            st.session_state.loaded_persona = persona
                            st.toast(f"📚 Context Loaded: {persona}", icon="✅")
                            time.sleep(2)
                            response = send_message_with_retry(st.session_state.chat_session, "Context loaded. Ask for Age.")
                            text = response.text

                # CALCULATE LOGIC
                if "CALCULATE(" in text:
                    try:
                        params = text.split("CALCULATE(")[1].split(")")[0]
                        data = {"age":30, "salary":0, "business":0, "rent":0, "inv80c":0, "med80d":0}
                        for part in params.split(","):
                            if "=" in part:
                                k, v = part.split("="); 
                                vc = ''.join(filter(str.isdigit, v.strip()))
                                if vc: data[k.strip()] = int(vc)
                        
                        # --- GET FULL RESULT OBJECT ---
                        res = calculate_tax_detailed(
                            data['age'], data['salary'], data['business'], 
                            data['rent'], data['inv80c'], data['med80d']
                        )
                        
                        tn = res['new']['breakdown']['total']
                        to = res['old']['breakdown']['total']
                        winner = "New Regime" if tn < to else "Old Regime"
                        savings = abs(tn - to)
                        
                        st.chat_message("assistant", avatar="🤖").markdown(f"""
                        ### 🧾 Tax Analysis
                        **Recommendation:** Go with **{winner}** (Save ₹{savings:,})
                        
                        | Component | **New Regime** | **Old Regime** |
                        | :--- | :--- | :--- |
                        | Taxable Income | ₹{res['new']['net']:,} | ₹{res['old']['net']:,} |
                        | Base Tax | ₹{res['new']['breakdown']['base']:,} | ₹{res['old']['breakdown']['base']:,} |
                        | Cess (4%) | ₹{res['new']['breakdown']['cess']:,} | ₹{res['old']['breakdown']['cess']:,} |
                        | **TOTAL** | **₹{tn:,}** | **₹{to:,}** |
                        """)
                        
                        # --- MAPPING SECTION (The fix you requested) ---
                        with st.expander("📂 View Deduction Mapping (For HR Portal)"):
                            st.markdown("Use these figures when declaring tax to your employer:")
                            st.markdown(f"""
                            | Your Input | Income Tax Section | Amount Deducted |
                            | :--- | :--- | :--- |
                            | Standard Ded. | **Sec 16(ia)** | ₹50,000 |
                            | Rent Paid | **Sec 10(13A)** (HRA) | ₹{res['old']['deductions']['hra']:,} |
                            | PF / LIC / PPF | **Sec 80C** | ₹{res['old']['deductions']['80c']:,} |
                            | Health Ins. | **Sec 80D** | ₹{res['old']['deductions']['80d']:,} |
                            """)
                            st.caption("*Note: Deductions apply primarily to the Old Regime.*")
                            
                            # Contextual Diagram Tag
                            st.markdown("")

                        st.session_state.chat_session.history.append({"role": "model", "parts": [f"Result: New={tn}, Old={to}"]})
                    except Exception as e: st.error(f"Calc Error: {e}")

                else:
                    if "LOAD(" not in text:
                        st.chat_message("assistant", avatar="🤖").markdown(text)

            except Exception as e: st.error(f"Error: {e}")