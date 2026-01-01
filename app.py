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
You are "TaxGuide AI", a