import urllib.request
import os
from pathlib import Path

def download_file(url, output_path):
    print(f"Downloading {url} to {output_path}...")
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
        data = response.read()
        out_file.write(data)
    print(f"Downloaded {len(data)} bytes.")

def main():
    docs_dir = Path(__file__).parent.parent / "sample_docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    docs = [
        {
            "url": "https://raw.githubusercontent.com/hwchase17/chat-your-data/master/state_of_the_union.txt",
            "filename": "state_of_the_union.txt"
        },
        {
            "url": "https://raw.githubusercontent.com/progit/progit2/main/book/01-introduction/sections/about-version-control.asc",
            "filename": "git_introduction.txt"
        },
        {
            "url": "https://raw.githubusercontent.com/python/peps/master/pep-0008.txt",
            "filename": "pep8.txt"
        }
    ]
    
    for doc in docs:
        download_file(doc["url"], docs_dir / doc["filename"])

if __name__ == "__main__":
    main()
