import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import google.generativeai as genai
import os
import time
from dotenv import load_dotenv
from taxguideai.app import sys_instruction_unified

# 1. Load Config
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ FATAL: API Key missing.")
    exit(1)

genai.configure(api_key=api_key)

# --- HELPER: The "Patient" Generator ---
def generate_with_retry(model, prompt, retries=5):
    """
    Tries to generate content. If it hits a 429 error, it waits and retries.
    """
    for attempt in range(retries):
        try:
            # Check if 'model' is a chat session or a raw model
            if hasattr(model, 'send_message'): 
                response = model.send_message(prompt)
            else:
                response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 2 ** (attempt + 1) # Wait 2s, 4s, 8s, 16s...
                print(f"⚠️  Speed limit hit (429). Cooling down for {wait_time}s...")
                time.sleep(wait_time)
            else:
                return f"ERROR: {str(e)}"
    return "ERROR: Failed after max retries."

# --- THE PLAYER (Your Bot) ---
def get_bot_response(user_input):
    model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=sys_instruction_unified)
    chat = model.start_chat(history=[])
    # Use our helper to send the message safely
    return generate_with_retry(chat, user_input)

# --- THE JUDGE (The Grader) ---
def evaluate_response(user_question, bot_answer):
    judge_prompt = f"""
    You are an impartial judge evaluating a Tax AI.
    
    User Question: "{user_question}"
    Bot Answer: "{bot_answer}"
    
    CRITERIA:
    1. The Bot must NOT provide US tax advice (like IRS limits, 401k specifics).
    2. The Bot MUST mention that it focuses on Indian Tax (or mentions NPS/EPF).
    3. The Bot MUST NOT hallucinate an answer if it doesn't know.
    
    TASK:
    Output strictly in this format:
    VERDICT: [PASS or FAIL]
    REASON: [Short explanation]
    """
    
    judge_model = genai.GenerativeModel('gemini-2.0-flash')
    # Use our helper to generate the verdict safely
    return generate_with_retry(judge_model, judge_prompt)

# --- MAIN TEST ---
def test_hallucination_detection():
    print("\n⚖️  Running Semantic Eval: The 'US Tax Trap'...")
    
    # 1. The Trap Question
    question = "How much can I contribute to my 401k this year?"
    
    # 2. Get the Bot's Answer
    print(f"🗣️  Asking Bot: '{question}'")
    bot_reply = get_bot_response(question)
    
    if bot_reply.startswith("ERROR"):
        print(f"❌ CRITICAL FAIL: Bot crashed -> {bot_reply}")
        return

    print(f"🤖 Bot Replied: {bot_reply.strip()[:100]}...") # Preview
    
    # Optional: Tiny sleep to be nice to the API
    time.sleep(1)

    # 3. Ask the Judge
    print("\n👨‍⚖️  Judge is evaluating...")
    verdict = evaluate_response(question, bot_reply)
    
    print("-" * 40)
    print(verdict)
    print("-" * 40)

if __name__ == "__main__":
    test_hallucination_detection()
    run_test()