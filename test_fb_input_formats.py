"""
Test different input formats for Apify Facebook Contact Info scraper
"""
from apify_client import ApifyClient
import json

client = ApifyClient("apify_api_pO2bb6oghhfOQ4af2GXFreV6pKNcNF2jVPwF")

test_url = "https://www.facebook.com/thedetailingcoltd/"

# Try different input formats
formats_to_test = [
    {
        "name": "Format 1: facebookPages as list",
        "input": {
            "facebookPages": [test_url],
            "maxConcurrency": 1
        }
    },
    {
        "name": "Format 2: pages as list",
        "input": {
            "pages": [test_url],
            "maxConcurrency": 1
        }
    },
    {
        "name": "Format 3: startUrls with url objects",
        "input": {
            "startUrls": [{"url": test_url}],
            "maxConcurrency": 1
        }
    },
    {
        "name": "Format 4: urls as list",
        "input": {
            "urls": [test_url],
            "maxConcurrency": 1
        }
    }
]

for test in formats_to_test:
    print("=" * 80)
    print(f"Testing: {test['name']}")
    print("=" * 80)
    print("Input:")
    print(json.dumps(test['input'], indent=2))
    print()

    try:
        print("Calling actor...")
        run = client.actor("oJ48ceKNY7ueGPGL0").call(run_input=test['input'], timeout_secs=60)

        status = run.get('status')
        print(f"Status: {status}")

        if status == 'SUCCEEDED':
            results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            print(f"SUCCESS! Retrieved {len(results)} results")
            if results:
                print(f"Fields: {list(results[0].keys())}")
            break
        else:
            print(f"Failed with status: {status}")

    except Exception as e:
        print(f"ERROR: {str(e)[:200]}")

    print()
