import os
import base64
import requests

GH_TOKEN = os.environ.get("GH_TOKEN")
REPO = "David212law/Price_bot"

if not GH_TOKEN:
    print("❌ GH_TOKEN not set")
    exit(1)

def upload_file(path, content):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    data = {
        "message": f"Auto: upload {path} [skip ci]",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": "main"
    }
    if sha:
        data["sha"] = sha
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        print(f"✅ Uploaded {path} ({len(content)} bytes)")
    else:
        print(f"❌ Failed {path}: {r.status_code} {r.text[:200]}")

import subprocess
for f in ["data/researcher_conservative.json", "data/researcher_aggressive.json"]:
    if os.path.exists(f):
        content = open(f).read()
        print(f"=== {f} size: {len(content)} chars ===")
        print(f"=== first 50: {content[:50]} ===")
        
        # Debug: git status
        result = subprocess.run(["git", "status", f], capture_output=True, text=True)
        print(f"=== git status: {result.stdout} ===")
        
        if len(content) > 2:
            upload_file(f, content)
        else:
            print(f"⚠️ {f} is empty")
    else:
        print(f"⚠️ {f} not found")
