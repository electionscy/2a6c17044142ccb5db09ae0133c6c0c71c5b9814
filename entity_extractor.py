#!/usr/bin/env python3
"""
Entity Extraction & Categorical Tagging using Gemini API
"""

import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(os.path.expanduser('~/.env'))
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

model = genai.GenerativeModel('models/gemini-2.5-flash')

def extract_entities(title, summary):
    prompt = f"""
Analyze this migration-related signal and extract entities.

TITLE: {title}
SUMMARY: {summary}

Return ONLY valid JSON (no markdown, no extra text):
{{
    "countries": ["list of country names"],
    "people": ["list of person names"],
    "organizations": ["list of org names like UN, IOM"],
    "locations": ["specific cities or regions"],
    "category": "ONE of: Border Crisis, Refugee Flow, Economic Migration, Humanitarian, Policy Change, Other",
    "confidence": 0.9
}}
"""
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Remove markdown if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        
        data = json.loads(text)
        
        return {
            "countries": data.get('countries', []),
            "people": data.get('people', []),
            "organizations": data.get('organizations', []),
            "locations": data.get('locations', []),
            "category": data.get('category', 'Other'),
            "confidence": float(data.get('confidence', 0.5))
        }
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {"countries": [], "people": [], "organizations": [], "locations": [], "category": "Other", "confidence": 0.0}

if __name__ == "__main__":
    title = "Greece tightens border controls amid migrant surge from Turkey"
    summary = "The Greek government announced stricter border enforcement at the Evros River. UN officials expressed concern about humanitarian conditions."
    
    print("Testing Entity Extraction...")
    result = extract_entities(title, summary)
    print(json.dumps(result, indent=2, ensure_ascii=False))
