import streamlit as st
import google.generativeai as genai
import os
import time
import re
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

# --- 3. KNOWLEDGE LOADER ---
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

# --- 4. CALCULATOR ENGINE (The Dual-Core) ---

# Core 1: The Generic Math Engine (Safe Eval)
def safe_math_eval(expression):
    """
    Safely evaluates simple math expressions from the AI.
    Allowed: digits, operators, parens, min, max, abs, round
    """
    try:
        # 1. Sanitize: Allow only safe characters
        allowed_chars = set("0123456789+-*/()., minaxbsound ")
        if not set(expression).issubset(allowed_chars):
            return "Error: Unsafe characters in formula."
        
        # 2. Evaluate in restricted scope
        safe_dict = {"min": min, "max": max, "abs": abs, "round": round}
        result = eval(expression, {"__builtins__": None}, safe_dict)
        
        # 3. Format result
        if isinstance(result, (int, float)):
            return f"{int(result):,}"
        return str(result)
    except Exception as e:
        return f"Error calculating: {e}"

# Core 2: The Full Regime Calculator (Deterministic)
def calculate_tax_detailed(age, salary, business_income, rent_paid, inv_80c, med_80d, custom_basic=0):
    std_deduction_new = 75000; std_deduction_old = 50000
    basic = custom_basic if custom_basic > 0 else (salary * 0.50)
    taxable_business = business_income * 0.50
    hra_exemption = max(0, rent_paid * 12 - (0.10 * basic))
    
    gross = salary + taxable_business
    deductions_old = std_deduction_old + hra_exemption + min(inv_80c, 150000) + med_80d
    net_old = max(0, gross - deductions_old)
    net_new = max(0, gross - std_deduction_new)

    bd_new = compute_tax_breakdown(net_new, age, "new")
    bd_old = compute_tax_breakdown(net_old, age, "old")
    
    return {
        "new": {"breakdown": bd_new, "net": net_new},
        "old": {"breakdown": bd_old, "net": net_old, "deductions": {"std": std_deduction_old, "hra": hra_exemption, "80c": min(inv_80c, 150000), "80d": med_80d}}
    }

def compute_tax_breakdown(income, age, regime):
    tax = 0
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

    surcharge = 0
    if income > 5000000:
        rate = 0.10 if income <= 10000000 else 0.15
        if income > 20000000: rate = 0.25
        if regime == "old" and income > 50000000: rate = 0.37
        surcharge = tax * rate

    cess = (tax + surcharge) * 0.04
    total = int(tax + surcharge + cess)
    return {"base": int(tax), "surcharge": int(surcharge), "cess": int(cess), "total": total}

# --- 5. THE TWO BRAINS ---

# Brain A: Calculator (The Interviewer)
sys_instruction_calc = """
You are "TaxGuide AI". 
**Goal:** Interview the user. Be concise.

**MEMORY RULE:** If the user states a number, REMEMBER IT.
If later you ask for a breakdown (Basic/HRA) and they say "I don't know":
1. Do NOT invent a new salary.
2. Use the previously stated total salary to estimate.
3. Assume Basic = 50% of the Stated Salary.

**LOGIC FLOW:**
1. **START:** Ask: "How do you earn your living?"
2. **DETECT & LOAD:** (Salary/Business -> LOAD)
3. **INTERVIEW:** Age -> Income -> Basic -> Deductions.
4. **CALCULATE:** Output `CALCULATE(...)` with basic=0 if estimated.
"""

# Brain B: The Professor (Now Universal Math Capable)
sys_instruction_rules = """
You are "TaxGuide AI".
**Goal:** Answer user questions comprehensively.

**CRITICAL RULE - UNIVERSAL MATH TOOL:**
You are NOT allowed to do mental math for ANY tax question (HRA, Capital Gains, Deductions).
Whenever a calculation is needed:
1. Identify the formula based on the Rules (PDF).
2. Construct a Python-valid math expression using `min`, `max`, `+`, `-`, `*`, `/`.
3. Output: `CALCULATE_MATH(expression)`
4. Wait for the result.

**Examples:**
- User: "What is my HRA exemption? (Rent=2L, Basic=5L)"
  Formula: `min(200000 - 0.10*500000, 0.50*500000)`
  Output: `CALCULATE_MATH(min(200000 - (0.10*500000), 0.50*500000))`

- User: "Tax on 2L LTCG?" (Rule: 12.5% above 1.25L)
  Output: `CALCULATE_MATH((200000 - 125000) * 0.125)`

**OUTPUT FORMAT:**
[Main Answer] ||| [Technical Details]

**LOGIC:**
1. DETECT CONTEXT -> LOAD
2. NEED MATH -> `CALCULATE_MATH(formula)`
3. NEED FULL REPORT -> `SWITCH_TO_CALC`
"""

# --- 6. UI HEADER ---
col1, col2 = st.columns([5, 1])
with col1: st.markdown("### 🇮🇳 TaxGuide AI")
with col2: 
    if st.button("🔄", help="Reset"):
        st.session_state.clear()
        st.rerun()

# --- 7. HELPER: MESSAGE RENDERER ---
def render_message(text, role, avatar):
    with st.chat_message(role, avatar=avatar):
        if "|||" in text:
            summary, details = text.split("|||", 1)
            st.markdown(summary.strip())
            with st.expander("📝 Read Detailed Explanation"):
                st.markdown(details.strip())
        else:
            st.markdown(text)

# --- 8. FORK LOGIC ---
if "mode" not in st.session_state:
    st.session_state.mode = None
    st.session_state.chat_session = None
    st.session_state.loaded_persona = None

# SCREEN 1: BUTTONS
if st.session_state.mode is None:
    st.markdown("#### 👋 How can I help you today?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💰 Calculate My Tax", use_container_width=True):
            st.session_state.mode = "CALC"
            model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction_calc)
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.chat_session.history.append({"role": "model", "parts": ["Hi! Let's calculate. Do you earn a Salary or run a Business?"]})
            st.rerun()
    with c2:
        if st.button("📚 Ask Tax Rules", use_container_width=True):
            st.session_state.mode = "RULES"
            model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction_rules)
            st.session_state.chat_session = model.start_chat(history=[])
            st.session_state.chat_session.history.append({"role": "model", "parts": ["I can explain rules or do quick spot-checks. What's your question?"]})
            st.rerun()

# SCREEN 2: CHAT
else:
    for msg in st.session_state.chat_session.history:
        text, role = "", ""
        if isinstance(msg, dict):
            role = msg.get("role"); parts = msg.get("parts", [])
            if parts and isinstance(parts[0], str): text = parts[0]
        else:
            role = msg.role; text = msg.parts[0].text
            
        if text and "LOAD" not in text and "Result:" not in text and "SWITCH_TO_CALC" not in text