import requests
import json
import asyncio
import time
import traceback
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
        print(f"No existing notified tokens file found at {file_path}. Creating new set.")
        return set()
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {file_path}. Creating new set.")
        return set()
    except Exception as e:
        print(f"Unexpected error loading tokens: {e}. Creating new set.")
        return set()

# Save notified tokens to file
def save_notified_tokens(tokens, file_path):
    try:
        with open(file_path, "w") as file:
            json.dump(list(tokens), file)
        print(f"Successfully saved {len(tokens)} notified tokens")
    except Exception as e:
        print(f"Error saving notified tokens: {e}")

# Fetch token updates from the API
def fetch_latest_tokens():
    retries = 3
    for attempt in range(retries):
        try:
            print(f"Fetching tokens from {DEX_API_URL}, attempt {attempt+1}/{retries}")
            response = requests.get(DEX_API_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"Successfully fetched {len(data)} tokens")
                return data
            else:
                print(f"Failed to fetch data: HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"Timeout occurred, retrying ({attempt + 1}/{retries})...")
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
        except json.JSONDecodeError:
            print(f"Error decoding API response as JSON")
        except Exception as e:
            print(f"Unexpected error fetching tokens: {e}")
    
    print("All fetch attempts failed")
    return None

# Send Telegram message
async def send_telegram_message(message):
    retries = 3
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
            print("Message sent successfully!")
            return True
        except Exception as e:
            print(f"Failed to send message: {e}. Retry {attempt + 1}/{retries}")
            print(f"Message length: {len(message)} characters")
            # If the message is too long, truncate it
            if len(message) > 4000 and attempt == retries - 1:
                message = message[:3900] + "...\n\n[Message truncated]"
            await asyncio.sleep(2)
    
    print("All send attempts failed")
    return False

# Main monitoring function
async def monitor_updates():
    print(f"Starting token monitor at {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    notified_tokens = load_notified_tokens(NOTIFIED_TOKENS_FILE)
    print(f"Loaded {len(notified_tokens)} previously notified tokens")
    
    loop_count = 0
    
    try:
        while True:
            loop_count += 1
            print(f"\n--- Check cycle #{loop_count} at {time.strftime('%Y-%m-%d %H:%M:%S UTC')} ---")
            
            try:
                data = fetch_latest_tokens()
                
                if data:
                    tokens_checked = 0
                    tokens_skipped_no_telegram = 0
                    tokens_skipped_already_notified = 0
                    tokens_notified = 0
                    
                    for token_idx, token in enumerate(data):
                        tokens_checked += 1
                        try:
                            # Extract basic token information
                            token_address = token.get("tokenAddress", "N/A")
                            
                            # Skip already notified tokens early
                            if token_address in notified_tokens:
                                tokens_skipped_already_notified += 1
                                if tokens_checked % 10 == 0:
                                    print(f"Processed {tokens_checked}/{len(data)} tokens, found {tokens_notified} new")
                                continue
                            
                            token_chain = token.get("chainId", "N/A")
                            token_description = token.get("description", "")
                            token_og_image = token.get("openGraph", None)
                            dexscreener_link = token.get("url", None)
                            
                            # Extract token name from appropriate fields
                            token_name = "Unknown Token"
                            
                            # Try to derive a name from the first line of the description
                            if token_description and token_name == "Unknown Token":
                                # Get the first line or first sentence that might contain the token name
                                first_line = token_description.split('\n')[0].strip()
                                # If there's a dollar sign prefix, it might be the token name
                                if '$' in first_line:
                                    dollar_parts = first_line.split('$')
                                    if len(dollar_parts) > 1:
                                        # Extract the token symbol after the $ sign
                                        potential_symbol = dollar_parts[1].split()[0].strip()
                                        if potential_symbol:
                                            token_name = potential_symbol
                            
                            # If we still don't have a name, try to use the first part of the token address
                            if token_name == "Unknown Token" and token_address != "N/A":
                                # For short addresses like on Solana, use as-is
                                # For long Ethereum-style addresses, use a shortened version
                                if len(token_address) < 15:  # Solana-style
                                    token_name = f"Token {token_address[:8]}..."
                                else:  # Ethereum-style
                                    token_name = f"Token {token_address[:6]}...{token_address[-4:]}"
                            
                            # Get links - improved for safer access
                            links = token.get("links", [])
                            telegram_link = None
                            website_link = None
                            twitter_link = None
                            
                            if links and isinstance(links, list):
                                # Try to find Telegram link by type first, then by URL content
                                telegram_link = next(
                                    (link.get("url") for link in links if isinstance(link, dict) and 
                                     (link.get("type") == "telegram" or 
                                      ("url" in link and "t.me" in link.get("url", "")))), 
                                    None
                                )
                                
                                # Find website link - typically labeled as "Website"
                                website_candidates = [
                                    link.get("url") for link in links if isinstance(link, dict) and 
                                    ((link.get("label") == "Website" or link.get("label") == "website") or 
                                     ("url" in link and "http" in link.get("url", "") and "t.me" not in link.get("url", "")))
                                ]
                                if website_candidates:
                                    website_link = website_candidates[0]
                                    
                                # Get Twitter/X link
                                twitter_link = next(
                                    (link.get("url") for link in links if isinstance(link, dict) and 
                                     (link.get("type") == "twitter" or 
                                      ("url" in link and ("twitter.com" in link.get("url", "") or "x.com" in link.get("url", ""))))), 
                                    None
                                )
                            
                            # Skip tokens without Telegram links
                            if not telegram_link:
                                tokens_skipped_no_telegram += 1
                                if tokens_checked % 10 == 0:
                                    print(f"Processed {tokens_checked}/{len(data)} tokens, found {tokens_notified} new")
                                continue
                            
                            # Create message format with image at the top
                            message = ""
                            if token_og_image:
                                message = f"<a href='{token_og_image}'> </a>"  # Space character to ensure image displays

                            # Add a concise header and token info
                            message += (
                                f"\n\n<b>🔔 NEW TOKEN: {token_name}</b>\n"
                                f"<b>⛓️ {token_chain.upper()}</b> | "
                            )
                            
                            # Add links in a compact horizontal format
                            if telegram_link:
                                message += f"<a href='{telegram_link}'>📱</a> "
                            if twitter_link:
                                message += f"<a href='{twitter_link}'>🐦</a> "
                            if website_link:
                                message += f"<a href='{website_link}'>🌐</a> "
                            if dexscreener_link:
                                message += f"<a href='{dexscreener_link}'>📊</a> "
                            
                            # Add contract and brief description
                            message += f"\n\n<code>{token_address}</code>"
                            
                            # Add a very brief description if available (just first 100 chars)
                            if token_description:
                                short_desc = token_description.split('\n')[0][:100]
                                if len(short_desc) > 0:
                                    message += f"\n\n<i>{short_desc}...</i>"

                            # Send the message
                            print(f"Sending message for token: {token_name} ({token_chain})")
                            send_success = await send_telegram_message(message)

                            if send_success:
                                # Only add to notified list if the message was successfully sent
                                notified_tokens.add(token_address)
                                tokens_notified += 1
                                
                                # Save periodically to avoid losing notification status
                                if tokens_notified % 3 == 0:
                                    save_notified_tokens(notified_tokens, NOTIFIED_TOKENS_FILE)
                                    
                            # Respect rate limits even if send failed
                            await asyncio.sleep(1)
                            
                        except Exception as e:
                            print(f"Error processing token #{token_idx}: {e}")
                            traceback.print_exc()
                            continue
                    
                    # Save again at the end of the cycle
                    save_notified_tokens(notified_tokens, NOTIFIED_TOKENS_FILE)
                    
                    # Print summary
                    print(f"\nCheck cycle #{loop_count} summary:")
                    print(f"- Tokens checked: {tokens_checked}")
                    print(f"- Skipped (no Telegram): {tokens_skipped_no_telegram}")
                    print(f"- Skipped (already notified): {tokens_skipped_already_notified}")
                    print(f"- New notifications sent: {tokens_notified}")
                    print(f"- Total tokens in notification list: {len(notified_tokens)}")
                    
                else:
                    print("No data received from API")
            
            except Exception as e:
                print(f"Error in check cycle #{loop_count}: {e}")
                traceback.print_exc()
            
            # Wait before the next check
            next_check_time = time.strftime('%Y-%m-%d %H:%M:%S UTC', 
                                          time.gmtime(time.time() + CHECK_INTERVAL))
            print(f"Waiting {CHECK_INTERVAL} seconds. Next check at {next_check_time}")
            await asyncio.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Critical error in main loop: {e}")
        traceback.print_exc()
    finally:
        # Make sure to save notifications before exiting
        save_notified_tokens(notified_tokens, NOTIFIED_TOKENS_FILE)
        print("Token monitor stopped")

if __name__ == "__main__":
    asyncio.run(monitor_updates())