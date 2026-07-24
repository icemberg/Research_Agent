import urllib.request
import json
import ssl
from pathlib import Path

def download_wiki_extract(title, output_path):
    print(f"Downloading Wikipedia article: {title}...")
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={title}&redirects=1&format=json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode('utf-8'))
            pages = data['query']['pages']
            page = list(pages.values())[0]
            extract = page.get('extract', '')
            
        if extract:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {page.get('title', title)}\n\n")
                f.write(extract)
            print(f"Saved {len(extract)} chars to {output_path}")
        else:
            print(f"Failed to get extract for {title}")
    except Exception as e:
        print(f"Error fetching {title}: {e}")

def main():
    docs_dir = Path(__file__).parent.parent / "sample_docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Python Zen (replaces PEP 8 for test)
    download_wiki_extract("Zen_of_Python", docs_dir / "python_best_practices.md")

if __name__ == "__main__":
    main()
