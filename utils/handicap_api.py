import requests

SCRAPER_URL = "https://lucienpb-handicap-scraper.hf.space/scrape"

def fetch_handicap(username, password, membership_number, fallback_name=None):
    """
    Calls the remote Handicap Scraper API hosted on Hugging Face.
    Returns (name, index) or raises an exception on failure.
    """

    payload = {
        "username": username,
        "password": password,
        "membership_number": membership_number,
        "fallback_name": fallback_name
    }

    try:
        response = requests.post(SCRAPER_URL, json=payload, timeout=45)
    except Exception as e:
        raise Exception(f"Network error calling Handicap API: {e}")

    if response.status_code != 200:
        raise Exception(f"Scraper API error: {response.text}")

    data = response.json()

    # API returns: {"name": "...", "index": "..."}
    return data.get("name"), data.get("index")
