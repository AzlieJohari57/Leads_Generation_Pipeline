import json

# Read notebook
print("Reading notebook...")
with open('Lead_Gen_Pipeline_Silver_4.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find the cell
print("Finding cell 3b0d9a99...")
for cell in nb['cells']:
    if cell.get('id') == '3b0d9a99':
        # Get source as string
        source = cell['source']
        if isinstance(source, list):
            source_str = ''.join(source)
        else:
            source_str = source

        # Replace the incorrect input format
        old_pattern = '    run_input = {\n        "pages": facebook_urls_batch,\n        "language": "en-US",\n        "maxConcurrency": MAX_CONCURRENCY  # FIXED: Added concurrency parameter\n    }'

        new_pattern = '    run_input = {\n        "startUrls": [{"url": url} for url in facebook_urls_batch],\n        "maxConcurrency": MAX_CONCURRENCY\n    }'

        if old_pattern in source_str:
            source_str = source_str.replace(old_pattern, new_pattern)
            cell['source'] = source_str
            print("OK: Fixed - Changed 'pages' parameter to 'startUrls' format")
        elif '"startUrls"' in source_str:
            print("OK: Cell already has startUrls - no change needed")
        else:
            print("WARN: Pattern not found - trying alternative pattern...")
            # Try with escaped quotes
            if '"pages"' in source_str:
                # Manual replacement
                source_str = source_str.replace(
                    '"pages": facebook_urls_batch',
                    '"startUrls": [{"url": url} for url in facebook_urls_batch]'
                )
                source_str = source_str.replace(
                    '"language": "en-US",\n',
                    ''
                )
                cell['source'] = source_str
                print("OK: Fixed - Used alternative replacement method")
            else:
                print("ERROR: Could not find pattern to replace")
        break

# Write back
print("Writing notebook...")
with open('Lead_Gen_Pipeline_Silver_4.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("\nOK: Notebook saved - close and reopen the notebook in VSCode!")
