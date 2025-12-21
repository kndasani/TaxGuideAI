import google.generativeai as genai
import numpy as np
import os
import pickle

# 1. SETUP API
# Paste your actual key here!
API_KEY = "AIzaSyBcQl1avm4MPpIMwW74EYFkuzlaaE8fsJ0"
genai.configure(api_key=API_KEY)

# 2. LOAD DATA
print("Loading tax rules...")
with open("tax_rules.txt", "r") as f:
    text = f.read()

# 3. CHUNK DATA
# Simple splitter: splits by paragraphs (double newlines)
documents = text.split("\n\n")
print(f"Split into {len(documents)} chunks.")

# 4. EMBED DATA (The "Memory")
print("Creating embeddings...")
embeddings = []
for doc in documents:
    # Get the embedding vector for each chunk
    result = genai.embed_content(
        model="models/embedding-001",
        content=doc,
        task_type="retrieval_document"
    )
    embeddings.append(result['embedding'])

# 5. SAVE TO DISK
# We save the text and the math vectors together
with open("manual_memory.pkl", "wb") as f:
    pickle.dump({"docs": documents, "vectors": embeddings}, f)

print("✅ Success! Memory created in 'manual_memory.pkl'")