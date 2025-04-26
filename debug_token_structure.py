import requests
import pprint

DEX_API_URL = "https://api.dexscreener.com/token-profiles/latest/v1"

def fetch_latest_tokens_v1():
    try:
        response = requests.get(DEX_API_URL, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch v1 data: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    return None

def main():
    print("Fetching v1 token profiles...")
    data = fetch_latest_tokens_v1()

    if data:
        print(f"\nTotal entries: {len(data)}\n")
        for i, token in enumerate(data[:5]):  # Print first 5 tokens
            print(f"------ v1 Token #{i+1} Structure ------")
            pprint.pprint(token, depth=4, width=120)
            print("\n")
    else:
        print("No data received from v1.")

if __name__ == "__main__":
    main()
