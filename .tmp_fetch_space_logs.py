import requests
from huggingface_hub import get_token

repo = "adityacyan/metahackathonr2-training"
token = get_token()
if not token:
    raise RuntimeError("No Hugging Face token found in local auth cache")

headers = {"Authorization": f"Bearer {token}"}
for kind in ["run", "build"]:
    url = f"https://huggingface.co/api/spaces/{repo}/logs/{kind}"
    print(f"===== {kind.upper()} LOGS ({url}) =====")
    r = requests.get(url, headers=headers, timeout=60)
    print("status:", r.status_code)
    text = r.text
    if len(text) > 20000:
        text = text[-20000:]
        print("[truncated to last 20000 chars]")
    print(text)
    print()
