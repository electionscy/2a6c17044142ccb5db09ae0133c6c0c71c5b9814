import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "").strip()
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

print(f"🔍 Έλεγχος διαθέσιμων μοντέλων για το κλειδί: {api_key[:10]}...")

try:
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print("\n✅ Επιτυχής σύνδεση! Τα διαθέσιμα μοντέλα σου είναι:")
        for m in models:
            print(f" - {m['name']}")
    else:
        print(f"❌ Σφάλμα {response.status_code}: {response.text}")
except Exception as e:
    print(f"❌ Αποτυχία σύνδεσης: {e}")