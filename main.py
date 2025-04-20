import requests
import json
import asyncio
import time
import pprint
from telegram import Bot

# Constants
DEX_API_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
NOTIFIED_TOKENS_FILE = "notified_tokens.json"
CHECK_INTERVAL = 60  # Check every 60 seconds
BOT_TOKEN = "7682084938:AAFVo5qUxqK9nbAjdrJHzaiUl66iUeDFw1o"
CHAT_ID = "-1002320564236"

# Initialize Telegram bot
bot = Bot(token=BOT_TOKEN)

# Load notified tokens from file
def load_notified_tokens(file_path):
    try:
        with open(file_path, "r") as file:
            return set(json.load(file))
    except FileNotFoundError:
        return set()

# Save notified tokens to file
def save_notified_tokens(tokens, file_path):
    with open(file_path, "w") as file:
        json.dump(list(tokens), file)

# Fetch token updates from the API
def fetch_latest_tokens():
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(DEX_API_URL, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch data: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"Timeout occurred, retrying ({attempt + 1}/{retries})...")
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
    return None

# Send Telegram message
async def send_telegram_message(message):
    retries = 3
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
            print("Message sent successfully!")
            return
        except Exception as e:
            print(f"Failed to send message: {e}. Retry {attempt + 1}/{retries}")
            await asyncio.sleep(2)

# Main monitoring function
async def monitor_updates():
    notified_tokens = load_notified_tokens(NOTIFIED_TOKENS_FILE)

    while True:
        print("Checking for updates...")
        data = fetch_latest_tokens()

        if data:
            for token in data:
                # Enhanced token name extraction with more fallback options
                # Try all possible locations for the token name
                token_name = token.get("name", "Unknown Token")
                
                # Checking all possible paths for token name
                if token_name == "Unknown Token":
                    # Try direct alternative field names
                    alt_fields = ["tokenName", "symbol", "baseSymbol", "ticker"]
                    for field in alt_fields:
                        if field in token and token[field]:
                            token_name = token[field]
                            break
                
                # Try nested objects if still Unknown
                if token_name == "Unknown Token":
                    # Check nested objects
                    nested_paths = [
                        ("baseTokenInfo", "name"),
                        ("tokenInfo", "name"),
                        ("profile", "name"),
                        ("token", "name"),
                        ("baseToken", "name"),
                        ("dexScreener", "name"),
                        ("pairInfo", "baseToken", "name"),
                        ("pairData", "baseToken", "name"),
                        ("baseToken", "symbol"),
                        ("tokenInfo", "symbol")
                    ]
                    
                    for path in nested_paths:
                        # Navigate the nested path
                        current = token
                        valid_path = True
                        
                        for key in path:
                            if isinstance(current, dict) and key in current:
                                current = current[key]
                            else:
                                valid_path = False
                                break
                        
                        if valid_path and current:
                            token_name = current
                            break
                
                # Debug print - log the token structure to understand its format
                if token_name == "Unknown Token":
                    print(f"DEBUG - Token with unknown name detected")
                    print(f"Token address: {token_address}")
                    print(f"Token fields: {', '.join(token.keys())}")
                    # Log first level of nested objects to avoid overwhelming output
                    for key, value in token.items():
                        if isinstance(value, dict):
                            print(f"  {key} contains: {', '.join(value.keys())}")
                        elif isinstance(value, list) and len(value) > 0:
                            print(f"  {key} is a list with {len(value)} items")
                
                token_address = token.get("tokenAddress", "N/A")
                token_chain = token.get("chainId", "N/A")
                
                # Get links
                links = token.get("links", [])
                telegram_link = next(
                    (link["url"] for link in links if "t.me" in link.get("url", "")), 
                    None
                )
                website_link = next(
                    (link["url"] for link in links if "http" in link.get("url", "") and "t.me" not in link.get("url", "")), 
                    None
                )
                dexscreener_link = token.get("url", None)

                # Skip tokens without Telegram links or already notified
                if not telegram_link:
                    print(f"Skipping {token_name} (no Telegram link).")
                    continue
                if token_address in notified_tokens:
                    print(f"Skipping {token_name} (already notified).")
                    continue

                # Format the notification message with beautiful styling
                message = (
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🚀 <b>NEW TOKEN DETECTED!</b> 🚀\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💎 <b>Token:</b> <code>{token_name}</code>\n"
                    f"⛓️ <b>Network:</b> <code>{token_chain}</code>\n"
                    f"📝 <b>Contract:</b>\n<code>{token_address}</code>\n\n"
                    f"📱 <b>Community:</b>\n<a href='{telegram_link}'>Telegram Group</a>\n"
                )
                if website_link:
                    message += f"🌐 <b>Website:</b>\n<a href='{website_link}'>Official Website</a>\n"
                if dexscreener_link:
                    message += f"\n📊 <a href='{dexscreener_link}'><b>View Chart on DEXScreener</b></a>\n"
                
                # Add a footer
                message += f"\n━━━━━━━━━━━━━━━━━━━━━\n⏰ <i>Detected at: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"

                # Send the message
                print(f"Sending message for token: {token_name}")
                await send_telegram_message(message)

                # Add token to notified list and save
                notified_tokens.add(token_address)
                save_notified_tokens(notified_tokens, NOTIFIED_TOKENS_FILE)

                # Respect rate limits
                await asyncio.sleep(1)
        else:
            print("No data received or no new tokens found.")

        # Wait before the next check
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(monitor_updates())