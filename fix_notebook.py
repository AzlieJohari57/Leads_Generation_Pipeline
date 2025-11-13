import json

# Read the notebook
with open('Optimizing_Apify.ipynb', 'r', encoding='utf-8') as f:
    notebook = json.load(f)

# Find cell 31c7e5a5 and replace it
new_code = '''client = ApifyClient("apify_api_xqctmgUBzh5ukWumUVT9SwlnOxEdft4dpNI6")

# CONFIG - 5 UENs per actor, RESIDENTIAL proxy
BATCH_SIZE = 5
MAX_CONCURRENCY = 3
MAX_RETRIES = 2

def create_optimized_pagefunction() -> str:
    """Search + Click flow v3.0"""
    return """
async function pageFunction(context) {
    const { page, log, request } = context;
    const uen = request?.userData?.uen || "";

    log.info(`🔎 SEARCH FLOW START for UEN: ${uen}`);

    if (!uen) {
        return { status: 'error', uen: null, error: 'Missing UEN' };
    }

    try {
        log.info(`➡️ Step 1: Loading homepage`);
        await page.goto("https://recordowl.com/", {
            waitUntil: 'networkidle2',
            timeout: 30000
        });
        await new Promise(r => setTimeout(r, 2000));

        log.info(`➡️ Step 2: Searching for "${uen}"`);
        const searchInput = "input[placeholder='Search company name, industry, or address']";
        await page.waitForSelector(searchInput, { timeout: 20000 });

        await page.click(searchInput, { clickCount: 3 });
        await page.keyboard.press('Backspace');
        await page.type(searchInput, uen, { delay: 100 });
        await new Promise(r => setTimeout(r, 500));

        await page.click("button[type='submit']");
        log.info(`➡️ Step 3: Waiting for search results`);

        try {
            await page.waitForNavigation({
                waitUntil: 'networkidle2',
                timeout: 20000
            });
        } catch (e) {
            log.info(`Navigation timeout - checking if results loaded`);
        }

        await new Promise(r => setTimeout(r, 2000));

        log.info(`➡️ Step 4: Click on the link to the company page on recordowl`);

        const linkFound = await page.evaluate((targetUen) => {
            const links = Array.from(document.querySelectorAll("a[href*='/company/']"));
            const uenUpper = targetUen.toUpperCase();

            for (const link of links) {
                const text = (link.innerText || "").toUpperCase();
                const href = link.href || "";

                if (text.includes(uenUpper) || href.toUpperCase().includes(uenUpper)) {
                    link.click();
                    return true;
                }
            }

            return false;
        }, uen);

        if (!linkFound) {
            log.info(`❌ No company link found for UEN: ${uen}`);
            return { status: 'not_found', uen };
        }

        log.info(`➡️ Step 5: Navigating to company page`);
        await page.waitForNavigation({
            waitUntil: 'networkidle2',
            timeout: 30000
        });
        await new Promise(r => setTimeout(r, 2500));

        log.info(`➡️ Step 6: Verifying UEN on page`);
        const pageUen = await page.evaluate(() => {
            const bodyText = document.body.innerText || "";
            const match = bodyText.match(/\\b([0-9]{9}[A-Z]|T[0-9]{2}[A-Z]{2}[0-9]{4}[A-Z]|[0-9]{8}[A-Z])\\b/);
            return match ? match[0] : null;
        });

        log.info(`Page UEN: ${pageUen}, Target UEN: ${uen}`);

        if (!pageUen || pageUen.toUpperCase() !== uen.toUpperCase()) {
            log.info(`⚠️ UEN mismatch - Expected: ${uen}, Found: ${pageUen}`);
            return { status: 'error', uen, error: 'UEN verification failed' };
        }

        log.info(`➡️ Step 7: Extracting data`);
        const extractedData = await page.evaluate(() => {
            const phones = Array.from(document.querySelectorAll('a[href^="tel:"]'))
                .map(a => a.href.replace('tel:', '').trim())
                .filter(p => p && /[0-9]/.test(p));

            const emails = Array.from(document.querySelectorAll('a[href^="mailto:"]'))
                .map(a => a.href.replace('mailto:', '').trim())
                .filter(e => e && e.includes('@'));

            const facebook = Array.from(document.querySelectorAll('a[href*="facebook.com"]'))
                .map(a => a.href);
            const linkedin = Array.from(document.querySelectorAll('a[href*="linkedin.com"]'))
                .map(a => a.href);
            const instagram = Array.from(document.querySelectorAll('a[href*="instagram.com"]'))
                .map(a => a.href);
            const tiktok = Array.from(document.querySelectorAll('a[href*="tiktok.com"]'))
                .map(a => a.href);

            const socialDomains = ['facebook.com', 'linkedin.com', 'instagram.com',
                                  'tiktok.com', 'twitter.com', 'youtube.com', 'x.com'];
            const websites = Array.from(document.querySelectorAll('a[href^="http"]'))
                .map(a => a.href)
                .filter(url => !socialDomains.some(d => url.includes(d)) &&
                              !url.includes('recordowl.com'));

            function extractField(label) {
                const labels = label.toLowerCase().split('|');
                for (const dt of document.querySelectorAll('dt')) {
                    const dtText = dt.textContent.toLowerCase().trim();
                    if (labels.some(l => dtText.includes(l))) {
                        const dd = dt.nextElementSibling;
                        if (dd && dd.tagName === 'DD') {
                            return dd.textContent.trim();
                        }
                    }
                }
                return null;
            }

            const address = extractField('registered address|address|office address');

            return {
                emails: emails.length ? [...new Set(emails)] : null,
                phones: phones.length ? [...new Set(phones)] : null,
                website: websites.length ? websites[0] : null,
                facebook: facebook.length ? [...new Set(facebook)] : null,
                linkedin: linkedin.length ? [...new Set(linkedin)] : null,
                instagram: instagram.length ? [...new Set(instagram)] : null,
                tiktok: tiktok.length ? [...new Set(tiktok)] : null,
                address: address
            };
        });

        log.info(`✅ SUCCESS for UEN: ${uen} | Phones: ${extractedData.phones ? extractedData.phones.length : 0}`);

        return {
            status: 'success',
            uen,
            url: page.url(),
            ...extractedData
        };

    } catch (err) {
        log.error(`❌ ERROR for UEN ${uen}: ${err.message}`);
        return { status: 'error', uen, error: err.message };
    }
}
"""

def run_apify_batch(client, uens):
    start_urls = [{"url": "https://recordowl.com/", "userData": {"uen": uen}} for uen in uens]

    run_input = {
        "startUrls": start_urls,
        "useChrome": True,
        "headless": True,
        "stealth": True,
        "pageFunction": create_optimized_pagefunction(),
        "maxRequestRetries": 2,
        "maxRequestsPerCrawl": len(start_urls),
        "maxConcurrency": MAX_CONCURRENCY,
        "pageLoadTimeoutSecs": 60,
        "pageFunctionTimeoutSecs": 120,
        "waitUntil": ["networkidle2"],
        "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        "proxyRotation": "RECOMMENDED",
    }

    for attempt in range(MAX_RETRIES):
        try:
            run = client.actor("apify/puppeteer-scraper").call(run_input=run_input)
            run_client = client.run(run["id"])
            run_info = run_client.wait_for_finish()

            if run_info.get("status") == "SUCCEEDED" and "defaultDatasetId" in run:
                dataset_check = client.dataset(run["defaultDatasetId"])
                time.sleep(1)
                test_items = dataset_check.list_items(limit=1, clean=True)

                if test_items.items and len(test_items.items) > 0:
                    return run, None
                elif attempt < MAX_RETRIES - 1:
                    time.sleep(15)
                    continue

            return run, None

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(15)
                continue
            return None, str(e)

    return None, "Max retries exceeded"

all_results = []
total_rows = len(acra_data_filtered_by_industry)
total_batches = (total_rows + BATCH_SIZE - 1) // BATCH_SIZE

print(f"\\n🚀 SEARCH+CLICK | {BATCH_SIZE} UENs/batch | Concurrency {MAX_CONCURRENCY} | RESIDENTIAL Proxy\\n")

for batch_idx in range(0, total_rows, BATCH_SIZE):
    batch = acra_data_filtered_by_industry.iloc[batch_idx:batch_idx + BATCH_SIZE]
    batch_num = (batch_idx // BATCH_SIZE) + 1
    uens = [str(row["UEN"]).strip() for _, row in batch.iterrows()]

    print(f"📦 Batch {batch_num}/{total_batches}: {', '.join(uens)}")

    run, error = run_apify_batch(client, uens)

    if error or not run or "defaultDatasetId" not in run:
        for uen in uens:
            all_results.append({
                "UEN": uen, "Status": "error", "Error": error or "No dataset",
                **{k: None for k in ['Emails', 'Phones', 'Website', 'Facebook', 'LinkedIn', 'Instagram', 'TikTok', 'address', 'RecordOwl_Link']}
            })
        continue

    time.sleep(3)
    dataset_client = client.dataset(run["defaultDatasetId"])

    try:
        items = list(dataset_client.iterate_items())
    except:
        items = []

    uen_to_item = {item.get("uen"): item for item in items if item.get("uen")}

    print("\\n📊 Results:")
    for uen in uens:
        item = uen_to_item.get(uen)

        if not item:
            all_results.append({
                "UEN": uen, "Status": "missing", "Error": "No data",
                **{k: None for k in ['Emails', 'Phones', 'Website', 'Facebook', 'LinkedIn', 'Instagram', 'TikTok', 'address', 'RecordOwl_Link']}
            })
            print(f"   ⚠️ {uen}: No data")
            continue

        status = item.get("status")
        phones = item.get("phones")

        if status == "success":
            all_results.append({
                "UEN": uen, "Status": "success",
                "Emails": item.get("emails"), "Phones": phones,
                "Website": item.get("website"), "Facebook": item.get("facebook"),
                "LinkedIn": item.get("linkedin"), "Instagram": item.get("instagram"),
                "TikTok": item.get("tiktok"), "address": item.get("address"),
                "RecordOwl_Link": item.get("url"), "Error": None
            })
            phone_display = ", ".join(phones) if phones else "None"
            print(f"   ✅ {uen}: {phone_display}")
        elif status == "not_found":
            all_results.append({
                "UEN": uen, "Status": "not_found", "Error": "Not found",
                **{k: None for k in ['Emails', 'Phones', 'Website', 'Facebook', 'LinkedIn', 'Instagram', 'TikTok', 'address', 'RecordOwl_Link']}
            })
            print(f"   ⚠️ {uen}: Not found")
        else:
            all_results.append({
                "UEN": uen, "Status": "error", "Error": item.get("error", "Unknown"),
                **{k: None for k in ['Emails', 'Phones', 'Website', 'Facebook', 'LinkedIn', 'Instagram', 'TikTok', 'address', 'RecordOwl_Link']}
            })
            print(f"   ❌ {uen}: {item.get('error', 'Error')}")

    print()
    time.sleep(10)

New_Fresh_Leads = pd.DataFrame(all_results)

if 'address' in New_Fresh_Leads.columns and 'UEN' in New_Fresh_Leads.columns:
    cols = list(New_Fresh_Leads.columns)
    cols.insert(1, cols.pop(cols.index('address')))
    New_Fresh_Leads = New_Fresh_Leads.loc[:, cols]

print(f"\\n✅ COMPLETE | Processed: {len(New_Fresh_Leads)} | Success: {(New_Fresh_Leads['Status'] == 'success').sum()}")
print(f"📞 Phone numbers found: {New_Fresh_Leads['Phones'].notna().sum()}")

New_Fresh_Leads.head(10)'''

for cell in notebook['cells']:
    if cell.get('id') == '31c7e5a5':
        cell['source'] = new_code
        print("OK: Found and updated cell 31c7e5a5")
        break

# Write back
with open('Optimizing_Apify.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)

print("OK: Notebook saved successfully!")
print("\nNow:")
print("1. Close the notebook in VSCode")
print("2. Reopen it")
print("3. Restart kernel and run")
