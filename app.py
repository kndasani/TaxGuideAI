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

# --- 3. THE CALCULATOR ENGINE ---
def calculate_tax_logic(age, salary, business_income, rent_paid, inv_80c, med_80d):
    std_deduction_new = 75000 
    std_deduction_old = 50000
    
    # Business Income (50% Presumptive)
    taxable_business = business_income * 0.50
    
    # Salary Income
    basic = salary * 0.50
    hra = max(0, rent_paid * 12 - (0.10 * basic))
    
    # Net Taxable Income
    gross_old = (salary - std_deduction_old - hra) + taxable_business
    taxable_old = max(0, gross_old - min(inv_80c, 150000) - med_80d)
    taxable_new = max(0, (salary - std_deduction_new) + taxable_business)

    return compute_slabs(taxable_new, taxable_old, age)

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

# --- 4. LOAD KNOWLEDGE ---
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

# --- 5. THE CONSULTANT BRAIN ---
sys_instruction = """
You are "TaxGuide AI", an expert and empathetic Indian Tax Consultant.
**Your Goal:** Guide the user to the best tax regime by discovering their details conversationally.

**PHASE 1: PERSONA DISCOVERY**
- Start by introducing yourself as TaxGuide AI.
- Ask: "To help you save the most tax, I need to understand how you earn. Do you earn a Salary, are you a Freelancer/Business owner, or both?"
- **Do NOT** ask for numbers yet. Just understand the source.

**PHASE 2: SLAB CLARIFICATION**
- Ask for their **AGE** (Critical for Senior Citizen slabs).
- Ask for their **Total Annual Income**.
- Explain *why* you are asking.

**PHASE 3: DEDUCTION HUNTING (The Guide)**
- **Do NOT** ask "What is your 80C?".
- Instead, ask **GUIDING QUESTIONS** like:
  - "Do you live in a rented house?" (for HRA)
  - "Do you have investments like PF, PPF, or Life Insurance?" (for 80C).
  - "Do you pay for medical insurance?" (for 80D).

**PHASE 4: EXECUTION**
- Only when you have all numbers, output strictly:
  `CALCULATE(age=..., salary=..., business=..., rent=..., inv80c=..., med80d=...)`
"""

# --- 6. HEADER & DISCLAIMER ---
col1, col2 = st.columns([5, 1])
with col1:
    st.markdown("###