import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load API key from your .env file
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

print("--- Checking for available Gemini models ---")

try:
    genai.configure(api_key=GEMINI_API_KEY)

    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(f"- {model.name}")
            
except Exception as e:
    print("\n!!! FAILED TO CONNECT TO GOOGLE AI !!!")
    print(f"Error: {e}")
    print("\nThis confirms the issue is with your API key or project setup.")
    print("Please ensure your GEMINI_API_KEY is correct in the .env file and that the 'Generative Language API' is enabled in your Google Cloud project.")
