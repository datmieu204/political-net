# chatbot/ner/core.py

import requests
from utils.config import settings

def extract_entities_relations(question: str) -> dict:
    """
    Extract entities and relations from question using NER service.
    Returns empty result if service unavailable.
    """
    payload = {"question": question}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(
            # settings.NER_SERVICE_URL,
            "https://64c7700e8751.ngrok-free.app/predict",
            headers=headers,
            json=payload, 
            timeout=60
        )
    except requests.exceptions.Timeout:
        print(f"[NER] Service timeout - continuing without NER")
        return {"entities": [], "relations": []}
    except requests.exceptions.ConnectionError:
        print(f"[NER] Service unavailable - continuing without NER")
        return {"entities": [], "relations": []}
    except requests.exceptions.RequestException as e:
        print(f"[NER] Service error: {e} - continuing without NER")
        return {"entities": [], "relations": []}
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[NER] Service error: {response.status_code} - continuing without NER")
        return {"entities": [], "relations": []}
