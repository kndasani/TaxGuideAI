import streamlit as st
import google.generativeai as genai
import pickle
import numpy as np
import os
import re
from tools import calculate_new_regime_tax, calculate_old_regime_tax

# 1. PAGE SETUP
st.set_page_config(page_title="TaxBuddy AI", page_icon="💰")
st.title("💰 TaxBuddy: Old vs New Regime Helper")

# 2. SETUP API
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = st.text_input("Enter Google API Key:", type="password")

if not api_key:
    st.info("Please enter your API Key to continue.")
    st.stop()

genai.configure(api_key=api_key)

# 3. LOAD MEMORY
@st.cache_resource
def load_memory():
    if not os.path.exists("manual_memory.pkl"):
        return None, None
    with open("manual_memory.pkl", "rb") as f:
        data = pickle.load(f)
    return data["docs"], np.array(data["vectors"])

docs, vectors = load_memory()

# 4. HELPER FUNCTIONS
def find_relevant_context(query):
    if vectors is None: return ""
    # We use the embedding model for search (this usually stays the same)
    model = "models/embedding-001" 
    try:
        query_embedding = genai.embed_content(model=model, content=query, task_type="retrieval_query")['embedding']
        dot_products = np.dot(vectors, query_embedding)
        top_indices = np.argsort(dot_products)[-3:][::-1]
        return "\n\n".join([docs[i] for i in top_indices])
    except Exception as e:
        return ""

def extract_income(query):
    # UPDATED: Using gemini-2.0-flash
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""
    Extract the annual income amount from this text as a plain integer. 
    Ignore currency symbols or words like 'lakhs'.
    Example: "Tax on 15 lakhs" -> 1500000
    Example: "My salary is 800000" -> 800000
    
    Text: "{query}"
    Return ONLY the number. If no number found, return 0.
    """
    try:
        response = model.generate_content(prompt).text.strip()
        return int(re.sub(r'\D', '', response)) 
    except:
        return 0

# 5. CHAT INTERFACE
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I can answer tax questions OR calculate your tax. Try asking: 'Calculate tax for 15 lakhs'."}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.spinner("Thinking..."):
        # AGENT LOGIC
        income = 0
        is_calculation = False
        
        # Check if user wants calculation
        if any(word in prompt.lower() for word in ["calculate", "compute", "what is my tax", "how much tax"]):
            income = extract_income(prompt)
            if income > 0:
                is_calculation = True

        if is_calculation:
            # CALCULATOR AGENT
            tax_new = calculate_new_regime_tax(income)
            tax_old = calculate_old_regime_tax(income)
            diff = abs(tax_new - tax_old)
            better = "New Regime" if tax_new < tax_old else "Old Regime"
            
            response = f"""
            **Income:** ₹{income:,}
            
            **📊 New Regime Tax:** ₹{tax_new:,}
            **🏛️ Old Regime Tax:** ₹{tax_old:,}
            
            **Verdict:** The **{better}** saves you ₹{diff:,}.
            """
        else:
            # RAG AGENT
            relevant_text = find_relevant_context(prompt)
            # UPDATED: Using gemini-2.0-flash
            model = genai.GenerativeModel('gemini-2.0-flash')
            final_prompt = f"""
            Answer based ONLY on the context below.
            CONTEXT: {relevant_text}
            QUESTION: {prompt}
            """
            response = model.generate_content(final_prompt).text
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.chat_message("assistant").write(response)