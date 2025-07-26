import requests
import asyncio
from time import sleep
from telegram import Bot
from flask import Flask
from threading import Thread

# Constants
DEX_API_URL = 'https://api.dexscreener.com/token-profiles/latest/v1'
BOT_TOKEN = '7724395426:AAE8gXFYSPC4DdkxHIbS4rK-mHbVB40bbJ0'
CHANNEL_ID = '-1002320564236'

bot = Bot(token=BOT_TOKEN)
processed_tokens = set()  # In-memory tracker

# Flask keep-alive server
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Fetch data from DEX Screener
def fetch_token_updates():
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
            sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
    return None

# Send message to Telegram
async def send_telegram_message(message):
    retries = 3
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='HTML')
            print("Message sent successfully!")
            return
        except Exception as e:
            print(f"Failed to send message: {e}. Retry {attempt + 1}/{retries}")
            await asyncio.sleep(2)

# Bot main logic
async def main():
    global processed_tokens
    try:
        print("Fetching latest token updates from DEX Screener...")
        data = fetch_token_updates()

        if not data:
            print("No data received from DEX Screener.")
            return

        for token in data:
            try:
                token_name = token.get('name', 'Unknown Token')
                token_address = token.get('tokenAddress', 'N/A')
                token_chain = token.get('chainId', 'N/A')

                telegram_link = 'N/A'
                if token.get('links'):
                    telegram_link = next((link['url'] for link in token['links'] if 't.me' in link.get('url', '')), 'N/A')

                # Skip tokens without Telegram links
                if telegram_link == 'N/A':
                    print(f"Skipping {token_name} as it does not have a Telegram link.")
                    continue

                # Skip already processed tokens
                if token_address in processed_tokens:
                    print(f"Skipping {token_name} as it has already been processed.")
                    continue

                processed_tokens.add(token_address)

                message = (
                    f"<b>New Token Update!</b>\n"
                    f"Name: {token_name}\n"
                    f"Chain: {token_chain}\n"
                    f"Address: <code>{token_address}</code>\n"
                    f"Telegram: {telegram_link}"
                )

                print(f"Sending message for token: {token_name}")
                await send_telegram_message(message)
                await asyncio.sleep(1)  # Respect rate limits
            except Exception as e:
                print(f"Error processing token: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Entry point
if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())