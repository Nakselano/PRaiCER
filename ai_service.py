import os
import json
import re
import requests
from dotenv import load_dotenv
from google import genai
from groq import Groq

load_dotenv()

gemini_key = os.getenv('GEMINI_API_KEY')
gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
groq_key = os.getenv('GROQ')
groq_client = Groq(api_key=groq_key) if groq_key else None
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")
hf_key = os.getenv('HF_TOKEN') #nie działa//nie zdążyłem zrobić


def clean_json_text(text: str) -> str:
    pattern = r"^```(?:json)?\s*(.*?)\s*```$"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def generate_ai_response(prompt: str, provider: str = "auto") -> str:
    if gemini_client:
        try:
            print("☁️ AI: Próba Gemini...")
            response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return clean_json_text(response.text)
        except Exception as e:
            print(f"⚠️ Błąd Gemini: {e}")

    if groq_client:
        try:
            print("⚡ AI: Próba Groq...")
            completion = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Błąd Groq: {e}")


def analyze_reviews_with_gemini(text: str) -> dict:
    prompt = f"Przeanalizuj opinie i zwróć JSON {{'summary': '...', 'pros': '...', 'cons': '...'}}. Opinie: {text}"
    res = generate_ai_response(prompt, provider="auto")
    try:
        json_match = re.search(r'(\{.*\})', res, re.DOTALL)
        return json.loads(json_match.group(1)) if json_match else json.loads(res)
    except:
        return {"summary": "Błąd analizy API.", "pros": "", "cons": ""}