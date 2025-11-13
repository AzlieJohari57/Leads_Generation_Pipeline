You are analyzing my Apify web scraping notebook: **@Lead_Gen_Pipeline_Silver_2 copy.ipynb (1–882)**.  
The notebook uses the **apify/puppeteer-scraper** actor to scrape Record Owl pages using UEN identifiers.

Do not make assumptions or invent missing details.  
If a part of the code, flow, or data source is unclear, explicitly point it out and request clarification instead of guessing.  
Your analysis and improvements must be grounded in the actual notebook content.

---

### 🔍 PRIMARY GOALS

1. **Analyze & Refactor Apify Code**
   - Focus on the Apify-related cells only.
   - Review all `Apify`, `Actor`, `Dataset`, and `RequestQueue` logic.
   - Summarize the current scraping flow (setup → navigation → extraction → storage).
   - Condense the code for readability:
     - Group related logic into clear, reusable helper functions.
     - Add descriptive inline comments and logical structure.
     - Use clear, consistent variable names.

2. **Scraping Efficiency & Reliability**
   - Optimize PuppeteerScraper logic to prevent 403 errors, captchas, and rate limits:
     - Add randomized user agents and dynamic delays.
     - Implement retry and proxy rotation strategies.
     - Apply throttling or exponential backoff when rate limits are detected.
   - Ensure **each Record Owl page** is scraped **once per UEN** and data is complete.
   - Inspect HTML structure (selectors, navigation flow) and only change logic based on verified structure.

3. **Cost Optimization**
   - Current cost: **$0.053 per UEN run** — must be reduced.
   - Identify key cost drivers: request volume, proxy usage, or actor runtime.
   - Suggest and/or implement:
     - Caching or batching UENs per run.
     - Avoid unnecessary page reloads or redundant API calls.
     - Tune concurrency and timeouts for optimal balance.
     - Evaluate if switching to `CheerioCrawler` or `PlaywrightCrawler` may reduce costs while maintaining accuracy.

4. **Data Validation & UEN Verification**
   - Implement strict verification before extraction:
     - Confirm the UEN on the scraped page matches the target UEN.
     - Only save data after validation passes.
   - Review for fallback logic that might scrape unrelated pages.
   - Add clear checks or retries if UEN mismatch occurs.

5. **Concurrency & Scaling**
   - Maintain **concurrency = 3 per actor** to achieve faster runs.
   - Ensure concurrency does not trigger rate limits or IP blocks.
   - Optionally, include adaptive concurrency logic that adjusts speed dynamically based on stability or blocking rate.

---

### 📦 EXPECTED OUTPUT
- A **refactored, modular, and optimized** version of the Apify scraping section.
- Inline comments explaining each major improvement.
- A short **cost and efficiency optimization summary** at the end.
- Reliable **UEN verification logic** ensuring accurate page-level data.
- Optional: a concise **architectural flow summary** (setup → crawl → validate → extract → store).

---

### 🎯 CONTEXT
The scraper targets around **1,000 UENs**.  
The goal is to maximize scraping speed and data accuracy while minimizing Apify run costs and avoiding 403 or rate-limit errors.
