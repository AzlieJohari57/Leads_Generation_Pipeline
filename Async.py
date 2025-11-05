import asyncio
import requests
import pandas as pd
import numpy as np
import glob
import os
import re
import time
from apify_client import ApifyClient
from bs4 import BeautifulSoup
import json
from requests.exceptions import HTTPError, ConnectionError
from urllib3.exceptions import ProtocolError
from concurrent.futures import ThreadPoolExecutor

# Configuration
client = ApifyClient("apify_api_yNR85etaHpLtBzPoVozVVXUsCZe54u2Ffog1")
MAX_CONCURRENT = 3  # Number of concurrent Apify runs (adjust based on your needs)

SOCIAL_MEDIA_DOMAINS = [
    "facebook.com", "linkedin.com", "instagram.com", "youtube.com",
    "tiktok.com", "twitter.com", "x.com", "pinterest.com"
]

def fetch_dataset_items_safe(dataset_client, max_retries=5, initial_wait=3):
    """Safely fetch dataset items with multiple retry strategies."""
    dataset_items = []
    
    for attempt in range(max_retries):
        try:
            # Strategy 1: Try using iterate_items() (streaming)
            try:
                dataset_items = list(dataset_client.iterate_items())
                if dataset_items:
                    return dataset_items
            except (HTTPError, ConnectionError, ProtocolError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = initial_wait * (2 ** attempt)  # Exponential backoff
                    print(f"  ⚠️ Iteration method failed (attempt {attempt + 1}/{max_retries}), trying direct fetch in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  ⚠️ Iteration method failed after all retries, trying direct fetch...")
            
            # Strategy 2: Try using list_items() (direct pagination)
            try:
                offset = 0
                limit = 100
                while True:
                    page = dataset_client.list_items(offset=offset, limit=limit, clean=True)
                    if not page.items:
                        break
                    dataset_items.extend(page.items)
                    if len(page.items) < limit:
                        break
                    offset += limit
                
                if dataset_items:
                    return dataset_items
            except (HTTPError, ConnectionError, ProtocolError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = initial_wait * (2 ** attempt)
                    print(f"  ⚠️ Direct fetch failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"  ❌ All fetch methods failed: {e}")
                    return []
                    
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = initial_wait * (2 ** attempt)
                print(f"  ⚠️ Unexpected error (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Failed after all retries: {e}")
                return []
    
    return dataset_items


async def process_uen_async(uen, idx, total, executor):
    """Process a single UEN asynchronously."""
    loop = asyncio.get_event_loop()
    
    print(f"\n🔎 Processing {uen} ({idx}/{total})")

    # Build pageFunction with proper escaping
    page_function = f"""
    async function pageFunction(context) {{
        const {{ page, log, request }} = context;
        const uen = "{uen}";
        log.info("Visiting RecordOwl for UEN: " + uen);

        try {{
            await page.waitForSelector("input[placeholder='Search company name, industry, or address']", {{ timeout: 30000 }});
            const input = await page.$("input[placeholder='Search company name, industry, or address']");
            await input.click({{ clickCount: 3 }});
            await input.type(uen, {{ delay: 100 }});

            await Promise.all([
                page.waitForNavigation({{ waitUntil: 'networkidle2', timeout: 60000 }}).catch(() => null),
                page.click("button[type='submit']")
            ]);

            // Wait for results with longer timeout
            try {{
                await page.waitForSelector("a[href*='/company/']", {{ timeout: 45000 }});
            }} catch (e) {{
                log.info("No company links found, might be not found");
                return {{ status: 'not_found', uen }};
            }}

            const companyLink = await page.$$eval("a[href*='/company/']", (links, uen) => {{
                for (const a of links) {{
                    const text = a.innerText || "";
                    const href = a.href || "";
                    if (text.includes(uen) || href.includes(uen.toLowerCase())) return a.href;
                }}
                return links.length > 0 ? links[0].href : null;
            }}, uen);

            if (!companyLink) return {{ status: 'not_found', uen }};

            if (page.url() !== companyLink) {{
                await page.goto(companyLink, {{ waitUntil: 'networkidle2', timeout: 60000 }});
            }}

            await new Promise(r => setTimeout(r, 3000)); // Increased wait time
            const html_content = await page.content();
            const title = await page.title();
            const url = page.url();

            return {{ status: 'success', uen, url, title, html_content }};
        }} catch (err) {{
            log.error("Error in pageFunction: " + err.message);
            return {{ status: 'error', uen, error: err.message }};
        }}
    }}
    """

    run_input = {
        "startUrls": [{"url": "https://recordowl.com/"}],
        "useChrome": True,
        "headless": True,
        "stealth": True,
        "pageFunction": page_function,
    }

    run = None
    try:
        # Start the run (using executor for blocking I/O)
        print(f"  📡 Starting Apify run for {uen}...")
        run = await loop.run_in_executor(
            executor,
            lambda: client.actor("apify/puppeteer-scraper").call(run_input=run_input)
        )
        
        # Wait for the run to finish (poll the status)
        print(f"  ⏳ Waiting for run to complete...")
        run_client = client.run(run["id"])
        await loop.run_in_executor(executor, run_client.wait_for_finish)
    except Exception as e:
        print(f"  ❌ Apify call failed for {uen}: {e}")
        return {
            "UEN": uen,
            "Emails": None,
            "Phones": None,
            "Website": None,
            "Facebook": None,
            "LinkedIn": None,
            "Instagram": None,
            "TikTok": None,
            "RecordOwl_Link": None,
            "Error": f"Apify call failed: {str(e)}"
        }

    if not run or "defaultDatasetId" not in run:
        print(f"  ⚠️ No valid dataset returned for {uen}")
        return {
            "UEN": uen,
            "Emails": None,
            "Phones": None,
            "Website": None,
            "Facebook": None,
            "LinkedIn": None,
            "Instagram": None,
            "TikTok": None,
            "RecordOwl_Link": None,
            "Error": "No dataset returned"
        }

    # Wait for dataset to be ready
    print(f"  ⏳ Waiting for dataset to be ready...")
    await asyncio.sleep(3)
    
    scraped_html, record_owl_url = None, None
    
    # Fetch dataset items with improved error handling
    dataset_items = await loop.run_in_executor(
        executor,
        lambda: fetch_dataset_items_safe(
            client.dataset(run["defaultDatasetId"]),
            max_retries=5,
            initial_wait=3
        )
    )
    
    # Process items
    for item in dataset_items:
        if item.get("status") == "success":
            scraped_html = item.get("html_content", "")
            record_owl_url = item.get("url")
            print(f"  ✅ Successfully scraped {uen}")
        elif item.get("status") == "not_found":
            print(f"  ⚠️ Company not found for UEN {uen}")
        elif item.get("status") == "error":
            print(f"  ❌ Error for {uen}: {item.get('error')}")

    if not scraped_html:
        print(f"  ⚠️ No HTML content retrieved for {uen}")
        return {
            "UEN": uen,
            "Emails": None,
            "Phones": None,
            "Website": None,
            "Facebook": None,
            "LinkedIn": None,
            "Instagram": None,
            "TikTok": None,
            "RecordOwl_Link": record_owl_url or None,
            "Error": "No HTML content retrieved"
        }

    # Parse HTML
    try:
        soup = BeautifulSoup(scraped_html, "html.parser")
        parent = soup.select_one("div.max-w-7xl.mx-auto.lg\\:py-6.sm\\:px-6.lg\\:px-8")

        emails, phones, website = [], [], None
        facebook_links, linkedin_links, instagram_links, tiktok_links = [], [], [], []

        if parent:
            # Extract emails
            for a in parent.select("a[href^=mailto]"):
                email = a.get("href", "").replace("mailto:", "").strip()
                if email and email not in emails and "@" in email:
                    emails.append(email)

            # ========== COMPREHENSIVE PHONE EXTRACTION ==========
            print(f"  🔍 Searching for phone numbers...")
            
            # Method 1: Look for tel: links (most reliable)
            tel_links = parent.select("a[href^='tel:'], a[href^='tel']")
            if tel_links:
                print(f"  📱 Found {len(tel_links)} tel: links")
            
            for a in tel_links:
                tel_href = a.get("href", "").replace("tel:", "").strip()
                tel_text = a.get_text(strip=True)
                print(f"  📞 Tel link - href: '{tel_href}', text: '{tel_text}'")
                
                # Extract all digits from tel link
                digits_only = re.sub(r"\D", "", tel_href)
                print(f"  🔢 Tel digits: {digits_only}")
                
                # Handle different digit lengths
                if len(digits_only) == 10 and digits_only.startswith("65") and digits_only[2] in "689":
                    formatted = "+" + digits_only
                    if formatted not in phones:
                        phones.append(formatted)
                        print(f"  ✅ Added from tel link (10 digits): {formatted}")
                elif len(digits_only) == 8 and digits_only[0] in "689":
                    formatted = "+65" + digits_only
                    if formatted not in phones:
                        phones.append(formatted)
                        print(f"  ✅ Added from tel link (8 digits): {formatted}")
                elif len(digits_only) > 10:
                    print(f"  🔍 Searching within {len(digits_only)} digits for valid pattern...")
                    found = False
                    for i in range(len(digits_only) - 9):
                        if digits_only[i:i+2] == "65" and digits_only[i+2] in "689":
                            formatted = "+" + digits_only[i:i+10]
                            if formatted not in phones:
                                phones.append(formatted)
                                print(f"  ✅ Added from tel link (extracted): {formatted}")
                            found = True
                            break
                    if not found:
                        if digits_only[-8] in "689":
                            formatted = "+65" + digits_only[-8:]
                            if formatted not in phones:
                                phones.append(formatted)
                                print(f"  ✅ Added from tel link (last 8 digits): {formatted}")
            
            # Method 2: Look in dt/dd structure with broader keywords
            dt_tags = parent.select("dt")
            if dt_tags:
                print(f"  📋 Found {len(dt_tags)} dt tags")
            
            for dt in dt_tags:
                dt_text = dt.get_text(strip=True).lower()
                exclude_keywords = ["officer", "charge", "employee", "shareholder", "director", "registration"]
                phone_keywords = ["contact number", "phone", "tel", "mobile", "call", "contact no"]
                
                is_phone_field = any(kw in dt_text for kw in phone_keywords)
                is_excluded = any(excl in dt_text for excl in exclude_keywords)
                
                if is_phone_field and not is_excluded:
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        number_text = dd.get_text(" ", strip=True)
                        print(f"  📝 Field '{dt_text}': {number_text}")
                        
                        all_digits = re.sub(r"\D", "", number_text)
                        print(f"  🔢 Extracted digits: {all_digits}")
                        
                        if len(all_digits) == 10 and all_digits.startswith("65") and all_digits[2] in "689":
                            formatted = "+" + all_digits
                            if formatted not in phones:
                                phones.append(formatted)
                                print(f"  ✅ Added from dt/dd (10 digits): {formatted}")
                        elif len(all_digits) == 8 and all_digits[0] in "689":
                            formatted = "+65" + all_digits
                            if formatted not in phones:
                                phones.append(formatted)
                                print(f"  ✅ Added from dt/dd (8 digits): {formatted}")
                        elif len(all_digits) > 10:
                            for i in range(len(all_digits) - 9):
                                if all_digits[i:i+2] == "65" and all_digits[i+2] in "689":
                                    potential_number = all_digits[i:i+10]
                                    formatted = "+" + potential_number
                                    if formatted not in phones:
                                        phones.append(formatted)
                                        print(f"  ✅ Added from dt/dd (extracted): {formatted}")
                                    break
            
            # Method 3: Search entire parent for phone patterns if none found
            if not phones:
                print(f"  🔎 No phones found yet, searching entire content...")
                full_text = parent.get_text()
                
                patterns = [
                    r"\+[\s\-]*65[\s\-]+[689][\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d",
                    r"\([\s\-]*65[\s\-]*\)[\s\-]*[689][\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d",
                    r"(?<!\d)65[\s\-]+[689][\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d(?!\d)",
                    r"(?<!\d)[689][\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d(?!\d)",
                ]
                
                for pattern_idx, pattern in enumerate(patterns, 1):
                    matches = re.findall(pattern, full_text)
                    if matches:
                        print(f"  🔍 Pattern {pattern_idx} found {len(matches)} potential matches")
                    
                    for match in matches:
                        digits = re.sub(r"\D", "", match)
                        print(f"  🔢 Pattern {pattern_idx} match: '{match.strip()}' → digits: '{digits}'")
                        
                        if len(digits) == 10 and digits.startswith("65") and digits[2] in "689":
                            formatted = "+" + digits
                            if formatted not in phones:
                                phones.append(formatted)
                                print(f"  ✅ Added from pattern {pattern_idx} (10 digits): {formatted}")
                        elif len(digits) == 8 and digits[0] in "689":
                            formatted = "+65" + digits
                            if formatted not in phones:
                                phones.append(formatted)
                                print(f"  ✅ Added from pattern {pattern_idx} (8 digits): {formatted}")
                        elif len(digits) > 10:
                            for i in range(len(digits) - 9):
                                if digits[i:i+2] == "65" and digits[i+2] in "689":
                                    potential = digits[i:i+10]
                                    formatted = "+" + potential
                                    if formatted not in phones:
                                        phones.append(formatted)
                                        print(f"  ✅ Added from pattern {pattern_idx} (extracted): {formatted}")
                                    break
            
            if phones:
                print(f"  ✅ Total phones found: {phones}")
            else:
                print(f"  ⚠️ WARNING: No phone numbers found for {uen}")
            # ========== END PHONE EXTRACTION ==========

            # Extract website
            valid_websites = []
            for a in parent.select("a[href^=http]"):
                href = a.get("href", "").strip()
                href_lower = href.lower()
                if not any(domain in href_lower for domain in SOCIAL_MEDIA_DOMAINS):
                    if not any(skip in href_lower for skip in ["recordowl", "apify.com"]):
                        if any(tld in href for tld in [".com", ".sg", ".net", ".org", ".co"]):
                            valid_websites.append(href)
            website = valid_websites[0] if valid_websites else None

        # Extract social media links from entire page
        for a in soup.find_all("a", href=True):
            href = a["href"].strip().lower()
            if "facebook.com" in href and href not in facebook_links:
                facebook_links.append(href)
            elif "linkedin.com" in href and href not in linkedin_links:
                linkedin_links.append(href)
            elif "instagram.com" in href and href not in instagram_links:
                instagram_links.append(href)
            elif "tiktok.com" in href and href not in tiktok_links:
                tiktok_links.append(href)

        result = {
            "UEN": uen,
            "Emails": emails if emails else None,
            "Phones": phones if phones else None,
            "Website": website,
            "Facebook": list(set(facebook_links)) if facebook_links else None,
            "LinkedIn": list(set(linkedin_links)) if linkedin_links else None,
            "Instagram": list(set(instagram_links)) if instagram_links else None,
            "TikTok": list(set(tiktok_links)) if tiktok_links else None,
            "RecordOwl_Link": record_owl_url,
        }
        print(f"  ✅ Processed {uen}: {len(emails) if emails else 0} emails, {len(phones) if phones else 0} phones")
        return result
        
    except Exception as e:
        print(f"  ❌ Error parsing HTML for {uen}: {e}")
        return {
            "UEN": uen,
            "Emails": None,
            "Phones": None,
            "Website": None,
            "Facebook": None,
            "LinkedIn": None,
            "Instagram": None,
            "TikTok": None,
            "RecordOwl_Link": record_owl_url or None,
            "Error": f"HTML parsing error: {str(e)}"
        }


async def run_async_scraper(dataframe, save_path="scraping_results.csv"):
    """
    Main async function to process all UENs.
    
    Usage:
        import pandas as pd
        import asyncio
        
        # Load your data
        df = pd.read_csv("your_file.csv")
        
        # Run async scraper
        results = asyncio.run(run_async_scraper(df, "output.csv"))
    """
    all_results = []
    total = len(dataframe)
    
    print(f"\n🚀 Starting async scraping for {total} UENs")
    print(f"⚙️ Max concurrent requests: {MAX_CONCURRENT}\n")
    
    # Create thread pool executor
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT * 2) as executor:
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        async def process_with_limit(idx, row):
            async with semaphore:
                uen = str(row["UEN"]).strip()
                result = await process_uen_async(uen, idx, total, executor)
                # Small delay between requests
                await asyncio.sleep(2)
                return result
        
        # Create all tasks
        tasks = [process_with_limit(idx, row) for idx, (_, row) in enumerate(dataframe.iterrows(), 1)]
        
        # Run all tasks concurrently (with semaphore limiting)
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(all_results):
            if isinstance(result, Exception):
                uen = str(dataframe.iloc[i]["UEN"]).strip()
                print(f"  ❌ Exception for {uen}: {result}")
                processed_results.append({
                    "UEN": uen,
                    "Emails": None,
                    "Phones": None,
                    "Website": None,
                    "Facebook": None,
                    "LinkedIn": None,
                    "Instagram": None,
                    "TikTok": None,
                    "RecordOwl_Link": None,
                    "Error": f"Exception: {str(result)}"
                })
            else:
                processed_results.append(result)
    
    # Save results
    New_Fresh_Leads = pd.DataFrame(processed_results)
    New_Fresh_Leads.to_csv(save_path, index=False)
    
    print("\n✅ Scraping complete!")
    print(f"\n📊 Results summary:")
    print(f"   Total processed: {len(New_Fresh_Leads)}")
    print(f"   With emails: {New_Fresh_Leads['Emails'].notna().sum()}")
    print(f"   With phones: {New_Fresh_Leads['Phones'].notna().sum()}")
    print(f"   With websites: {New_Fresh_Leads['Website'].notna().sum()}")
    print(f"\n💾 Results saved to: {save_path}")
    
    return New_Fresh_Leads


# Main execution - modify this section with your actual data
if __name__ == "__main__":
    import pandas as pd
    
    print("🚀 Starting Async Lead Generation Scraper\n")
    
    # ==================== CONFIGURE YOUR DATA SOURCE HERE ====================
    # Uncomment and modify ONE of the options below:
    
    # Option 1: Load from CSV (default)
    print("📂 Loading data from CSV...")
    acra_data_filtered_wholesale_10 = pd.read_excel("Fresh_Leads.xlsx").head(6)
    
    # Option 2: Load from Excel
    # print("📂 Loading data from Excel...")
    # acra_data_filtered_wholesale_10 = pd.read_excel("Fresh_Leads.xlsx").head(10)
    
    # Option 3: Load from ACRA data files with filtering
    # print("📂 Loading ACRA data files...")
    # all_files = glob.glob("Acra_Data/*.csv")
    # acra_data = pd.concat([pd.read_csv(f) for f in all_files], ignore_index=True)
    # # Filter by SSIC code (example: wholesale trade = 46xxx)
    # acra_data_filtered_wholesale_10 = acra_data[acra_data['primary_ssic_code'].str.startswith('46')].head(10)
    
    # Option 4: Load specific ACRA file
    # print("📂 Loading specific ACRA file...")
    # acra_data = pd.read_csv("Acra_Data/ACRAInformationonCorporateEntitiesA.csv")
    # acra_data_filtered_wholesale_10 = acra_data.head(10)
    
    # =========================================================================
    
    print(f"✅ Loaded {len(acra_data_filtered_wholesale_10)} UENs to process\n")
    
    # Run the async scraper
    results = asyncio.run(run_async_scraper(
        acra_data_filtered_wholesale_10, 
        "async_scraping_results.csv"
    ))
    
    print("\n🎉 Done! Check async_scraping_results.csv for results")
