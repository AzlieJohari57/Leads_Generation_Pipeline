import requests
import pandas as pd
import time
import os

# Load the data
parquet_path = "./Staging/Gold/cleaned_second_592.parquet"
if os.path.exists(parquet_path):
    RecordOwl_Leads = pd.read_parquet(parquet_path, engine="fastparquet")
    print(f"Loaded {len(RecordOwl_Leads)} rows from {parquet_path}\n")
else:
    raise FileNotFoundError(f"Parquet file not found at {parquet_path}")

# Use first 10 companies for testing
companies_df = RecordOwl_Leads[["ACRA REGISTERED NAME", "Brand/Deal Name/Business Name"]].head(10).copy()

# API Configuration
API_KEY = "15304a36-d527-4f30-b250-b79cd409a464"
BASE_URL = "https://api.lusha.com"
CONTACT_SEARCH_ENDPOINT = f"{BASE_URL}/prospecting/contact/search"
CONTACT_ENRICH_ENDPOINT = f"{BASE_URL}/prospecting/contact/enrich"

headers = {
    "api_key": API_KEY,
    "Content-Type": "application/json"
}

# OPTIMIZED: Search all companies at once instead of one-by-one
def search_all_companies_optimized(company_names, batch_size=40):
    """
    Search for contacts across ALL companies in batches to minimize credit usage

    Instead of 1 credit per company, we search in batches of up to 40 companies
    for 1 credit per batch (up to 40 results)
    """
    all_contacts_by_company = {}
    total_credits = 0

    # Process companies in batches
    for batch_start in range(0, len(company_names), batch_size):
        batch = company_names[batch_start:batch_start + batch_size]

        print(f"\n{'='*80}")
        print(f"BATCH {batch_start//batch_size + 1}: Searching {len(batch)} companies in ONE request")
        print(f"{'='*80}")

        # Search for ALL companies in this batch at once
        payload = {
            "pages": {"page": 0, "size": batch_size},
            "filters": {
                "contacts": {
                    "include": {"existing_data_points": ["phone", "mobile_phone"]}
                },
                "companies": {
                    "include": {"names": batch}  # Search multiple companies at once!
                }
            }
        }

        try:
            response = requests.post(CONTACT_SEARCH_ENDPOINT, headers=headers, json=payload)

            if response.status_code in [200, 201]:
                data = response.json()
                contacts = data.get('data', [])
                request_id = data.get('requestId', '')
                credits = data.get('billing', {}).get('creditsCharged', 0)
                total_credits += credits

                print(f"[OK] Found {len(contacts)} total contacts across {len(batch)} companies")
                print(f"[OK] Credits charged: {credits} (vs {len(batch)} if searched individually)")
                print(f"[OK] Savings: {len(batch) - credits} credits!")

                # Group contacts by company
                for contact in contacts:
                    company = contact.get('companyName', '')
                    if company not in all_contacts_by_company:
                        all_contacts_by_company[company] = []
                    all_contacts_by_company[company].append({
                        'contact': contact,
                        'request_id': request_id
                    })

                time.sleep(0.1)
            else:
                print(f"[ERROR] Search Error {response.status_code}: {response.text[:200]}")

        except Exception as e:
            print(f"[ERROR] Exception: {str(e)}")

    print(f"\n{'='*80}")
    print(f"[CREDITS] Total search credits used: {total_credits} (vs {len(company_names)} individual searches)")
    print(f"[SAVINGS] Credit savings: {len(company_names) - total_credits}")
    print(f"{'='*80}\n")

    return all_contacts_by_company, total_credits

# Function to enrich contacts
def enrich_contacts_batch(request_id, contact_ids):
    """Enrich multiple contacts at once"""
    if not contact_ids:
        return {}

    enrich_payload = {
        "requestId": request_id,
        "contactIds": contact_ids
    }

    try:
        response = requests.post(CONTACT_ENRICH_ENDPOINT, headers=headers, json=enrich_payload)

        if response.status_code in [200, 201]:
            data = response.json()

            phone_map = {}
            if data.get('contacts') and isinstance(data['contacts'], list):
                for contact in data['contacts']:
                    contact_id = contact.get('id') or contact.get('contactId')
                    phones = contact.get('data', {}).get('phoneNumbers', [])

                    if phones and len(phones) > 0:
                        phone_map[contact_id] = phones[0].get('number', 'N/A')
                    else:
                        phone_map[contact_id] = 'N/A'

            return phone_map
        else:
            print(f"  Enrich Error {response.status_code}")
            return {}

    except Exception as e:
        print(f"  Enrich Exception: {str(e)}")
        return {}

# Main optimized function
def get_company_contacts_optimized(companies_df):
    """
    OPTIMIZED: Get first contact for each company with minimal credit usage
    """
    company_names = companies_df['ACRA REGISTERED NAME'].tolist()

    # Step 1: Search all companies in batches (1 credit per 40 companies instead of 1 per company!)
    contacts_by_company, search_credits = search_all_companies_optimized(company_names, batch_size=40)

    # Step 2: Enrich only the first contact per company
    results = []
    enrich_credits = 0

    print("\n" + "="*80)
    print("ENRICHING FIRST CONTACT PER COMPANY")
    print("="*80)

    for company_name in company_names:
        # Find matching company (case-insensitive partial match)
        matched_company = None
        for key in contacts_by_company.keys():
            if company_name.upper() in key.upper() or key.upper() in company_name.upper():
                matched_company = key
                break

        if matched_company and contacts_by_company[matched_company]:
            contact_data = contacts_by_company[matched_company][0]
            contact = contact_data['contact']
            request_id = contact_data['request_id']

            contact_id = contact.get('contactId')
            contact_name = contact.get('name', 'N/A')
            contact_title = contact.get('jobTitle', 'N/A')

            print(f"\n{company_name}:")
            print(f"  > {contact_name} ({contact_title})")

            # Enrich to get phone
            if contact_id and request_id:
                phone_map = enrich_contacts_batch(request_id, [contact_id])
                phone_number = phone_map.get(contact_id, 'N/A')
                enrich_credits += 1

                if phone_number and phone_number != 'N/A':
                    print(f"  [OK] Phone: {phone_number}")
                else:
                    print(f"  [NONE] No phone available")
            else:
                phone_number = 'N/A'

            results.append({
                'Company': company_name,
                'First_Contact_Name': contact_name,
                'First_Contact_Title': contact_title,
                'First_Contact_Number': phone_number
            })

            time.sleep(0.1)
        else:
            print(f"\n{company_name}: No contacts found")
            results.append({
                'Company': company_name,
                'First_Contact_Name': 'N/A',
                'First_Contact_Title': 'N/A',
                'First_Contact_Number': 'N/A'
            })

    print(f"\n{'='*80}")
    print(f"[CREDITS] TOTAL CREDITS USED:")
    print(f"   Search: {search_credits} credits")
    print(f"   Enrich: {enrich_credits} credits")
    print(f"   Total: {search_credits + enrich_credits} credits")
    print(f"\n[SAVINGS] vs individual search: {len(company_names) - search_credits} credits!")
    print(f"{'='*80}\n")

    return pd.DataFrame(results)

# Run optimized version
print("="*80)
print("OPTIMIZED COMPANY CONTACT SEARCH - TESTING WITH 10 COMPANIES")
print("="*80)
print(f"\nCompanies to search:")
for i, name in enumerate(companies_df['ACRA REGISTERED NAME'].tolist(), 1):
    print(f"  {i}. {name}")

results_df = get_company_contacts_optimized(companies_df)

print("\nFINAL RESULTS:")
print("="*80)
print(results_df.to_string(index=False))

# Add to dataframe
companies_df['First_Contact_Name'] = results_df['First_Contact_Name']
companies_df['First_Contact_Title'] = results_df['First_Contact_Title']
companies_df['First_Contact_Number'] = results_df['First_Contact_Number']

print("\n\nUPDATED DATAFRAME:")
print("="*80)
print(companies_df.to_string(index=False))
