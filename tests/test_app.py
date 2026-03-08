import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import time
from taxguideai.app import sys_instruction_unified
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. Load Environment
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ FATAL: API Key missing in .env file")
    exit(1)

genai.configure(api_key=api_key)

# 2. Robust Chat Function with Backoff
def get_bot_response(user_input, retries=3):
    """Simulates a chat with retry logic for 429 errors"""
    model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction_unified)
    chat = model.start_chat(history=[])
    
    for attempt in range(retries):
        try:
            response = chat.send_message(user_input)
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 2 ** (attempt + 1) # Exponential backoff: 2s, 4s, 8s...
                print(f"⚠️ Hit Rate Limit (429). Waiting {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                return f"ERROR: {str(e)}"
    
    return "ERROR: Failed after max retries."

def test_80c_recognition():
    print("\n🧪 Running Test: 80C Recognition...")
    
    input_text = "My salary is 30L. I don't pay rent, but I put 1.5L in PPF."
    response = get_bot_response(input_text)
    
    # CRITICAL: Fail fast if the API failed
    if response.startswith("ERROR"):
        print(f"❌ FAIL: API Error - {response}")
        return

    print(f"🤖 Bot Output: {response[:100]}...") # Print first 100 chars

    # --- ASSERTION 1: Data Extraction ---
    # We look for the specific tool parameter
    if "inv80c=150000" in response:
        print("✅ PASS: Data extraction successful.")
    else:
        print("❌ FAIL: Bot missed the PPF investment.")

    # --- ASSERTION 2: Context Awareness ---
    # Check for "Optimization Tips" regarding 80C
    # We look for keywords like "80C" appearing in the *text* part of a response
    # Since the tool call also has "inv80c", we must be careful.
    # A simple check: If it asks "Do you have 80C?" or "invest in PF", that's a fail.
    
    nagging_phrases = [
        "haven't included 80C",
        "save tax on up to ₹1.5L",
        "Do you have PF",
        "invest in PPF"
    ]
    
    found_nag = any(phrase in response for phrase in nagging_phrases)
    
    if found_nag:
        print("❌ FAIL: Bot is nagging about 80C despite valid input.")
    else:
        print("✅ PASS: Bot correctly stayed silent on 80C.")

if __name__ == "__main__":
    test_80c_recognition()