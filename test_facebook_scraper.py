"""
Test script to verify Apify Facebook Page Contact Information scraper
"""
from apify_client import ApifyClient
import json

# Initialize client
client = ApifyClient("apify_api_pO2bb6oghhfOQ4af2GXFreV6pKNcNF2jVPwF")

# Test with a single Facebook page
test_url = "https://www.facebook.com/thedetailingcoltd/"

print("=" * 80)
print("TESTING APIFY FACEBOOK PAGE CONTACT INFO SCRAPER")
print("=" * 80)
print(f"Test URL: {test_url}")
print(f"Actor ID: oJ48ceKNY7ueGPGL0")
print()

# Prepare input - CORRECT FORMAT from working code
run_input = {
    "startUrls": [
        {
            "url": test_url
        }
    ],
    "maxConcurrency": 1
}

print("Input structure:")
print(json.dumps(run_input, indent=2))
print()

try:
    print("Calling actor...")
    run = client.actor("oJ48ceKNY7ueGPGL0").call(run_input=run_input)

    print(f"Run ID: {run['id']}")
    print(f"Status: {run.get('status')}")
    print()

    # Get results
    print("Fetching results...")
    results = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        results.append(item)

    print(f"Retrieved {len(results)} result(s)")
    print()

    if results:
        print("=" * 80)
        print("FIRST RESULT:")
        print("=" * 80)
        print(json.dumps(results[0], indent=2, default=str))
        print()

        print("=" * 80)
        print("AVAILABLE FIELDS:")
        print("=" * 80)
        for key in results[0].keys():
            value = results[0][key]
            print(f"  - {key}: {type(value).__name__} = {value}")

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    print(traceback.format_exc())
