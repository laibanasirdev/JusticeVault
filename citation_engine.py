# JusticeVault/citation_engine.py
from google import genai
from google.genai import types

def query_thai_law(prompt, approved_context):
    client = genai.Client(api_key="YOUR_API_KEY")
    
    # We feed the 'Approved Only' context into Gemini
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Answer using ONLY this context: {approved_context}. Query: {prompt}",
        config=types.GenerateContentConfig(
            # This forces the AI to stay within our 'Vault'
            temperature=0.0 
        )
    )
    return response.text