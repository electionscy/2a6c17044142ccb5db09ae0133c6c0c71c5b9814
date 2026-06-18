#!/usr/bin/env python3
"""
Entity Extraction & Categorical Tagging using Gemini API
"""

import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv("/home/agent/migration_agent/.env")
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def extract_entities(title, summary):
    # Κράτα μόνο τα πρώτα 500 chars του summary για να αποφύγεις raw HTML
    clean_summary = str(summary)[:500] if summary else ""

    prompt = f"""Analyze this migration-related news signal and extract structured data.

TITLE: {title}
SUMMARY: {clean_summary}

Return ONLY valid JSON (no markdown, no extra text):
{{
    "countries": ["list of country names mentioned"],
    "people": ["list of person names"],
    "organizations": ["list of orgs like UN, IOM, Frontex"],
    "locations": ["specific cities or regions"],
    "category": "ONE of: Border Crisis, Refugee Flow, Economic Migration, Humanitarian, Policy Change, Other",
    "confidence": 0.9,
    "summary_el": "Περίληψη στα ελληνικά σε 2-3 προτάσεις",
    "primary_country": "η πιο σχετική χώρα ή κενό αν δεν υπάρχει"
}}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
        return {
            "countries": data.get("countries", []),
            "people": data.get("people", []),
            "organizations": data.get("organizations", []),
            "locations": data.get("locations", []),
            "category": data.get("category", "Other"),
            "confidence": float(data.get("confidence", 0.5)),
            "summary_el": data.get("summary_el", ""),
            "primary_country": data.get("primary_country", "")
        }
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "countries": [], "people": [], "organizations": [],
            "locations": [], "category": "Other", "confidence": 0.0,
            "summary_el": "", "primary_country": ""
        }

if __name__ == "__main__":
    title = "Greece tightens border controls amid migrant surge from Turkey"
    summary = "The Greek government announced stricter border enforcement at the Evros River."
    print("Testing Entity Extraction...")
    result = extract_entities(title, summary)
    print(json.dumps(result, indent=2, ensure_ascii=False))
