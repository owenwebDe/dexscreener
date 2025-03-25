import requests
import json
import asyncio
import time
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
                token_name = token.get("name", "Unknown Token")
                token_address = token.get("tokenAddress", "N/A")
                token_chain = token.get("chainId", "N/A")
                telegram_link = next(
                    (link["url"] for link in token.get("links", []) if "t.me" in link.get("url", "")), 
                    None
                )
                website_link = next(
                    (link["url"] for link in token.get("links", []) if "http" in link.get("url", "") and "t.me" not in link.get("url", "")), 
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

                # Format the notification message
                message = (
                    f"🚀 <b>New Token Alert!</b>\n"
                    f"🔹 <b>Name:</b> {token_name}\n"
                    f"🔹 <b>Chain:</b> {token_chain}\n"
                    f"🔹 <b>Address:</b> <code>{token_address}</code>\n"
                    f"🔗 <b>Telegram:</b> <a href='{telegram_link}'>{telegram_link}</a>\n"
                )
                if website_link:
                    message += f"🌐 <b>Website:</b> <a href='{website_link}'>Visit Website</a>\n"
                if dexscreener_link:
                    message += f"📊 <b>DEX Screener:</b> <a href='{dexscreener_link}'>View on DEX Screener</a>\n"

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
