import requests
import time
import json
import os
from datetime import datetime

API_URL = "https://z519wdyajg.execute-api.us-east-1.amazonaws.com/prod/listings?limit=50&type=PLAYER&status=AVAILABLE&ageMax=25&overallMin=65&isFreeAgent=false&view=full"
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
CACHE_FILE = 'notified_players.json'

def load_notified_players():
    """Load previously notified player IDs from cache"""
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                return set(json.load(f))
    except Exception as e:
        print(f"Error loading cache: {e}")
    return set()

def save_notified_players(notified_ids):
    """Save notified player IDs to cache"""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(list(notified_ids), f)
    except Exception as e:
        print(f"Error saving cache: {e}")

def send_discord_message(player_id, player_info):
    """Send a Discord webhook message for a single player"""
    if not DISCORD_WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set in secrets")
        return False
    
    player_url = f"https://app.playmfl.com/players/{player_id}"
    
    # Create embedded message with player details
    embed = {
        "title": f"🔥 Revenue Share Player Found!",
        "description": f"**{player_info['name']}** (ID: {player_id})",
        "url": player_url,
        "color": 3447003,  # Blue color
        "fields": [
            {
                "name": "Revenue Share",
                "value": f"{player_info['revenue_share']}%",
                "inline": True
            },
            {
                "name": "Overall",
                "value": str(player_info['overall']),
                "inline": True
            },
            {
                "name": "Age",
                "value": str(player_info['age']),
                "inline": True
            },
            {
                "name": "Position(s)",
                "value": ", ".join(player_info['positions']),
                "inline": True
            },
            {
                "name": "Price",
                "value": f"{player_info['price']} USDC",
                "inline": True
            },
            {
                "name": "Nationality",
                "value": ", ".join(player_info['nationalities']),
                "inline": True
            }
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {
            "text": "MFL Listing Monitor"
        }
    }
    
    payload = {
        "content": f"🚨 **New Revenue Share Listing** 🚨\n{player_url}",
        "embeds": [embed]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print(f"✅ Sent Discord notification for player {player_id}")
            return True
        else:
            print(f"❌ Discord webhook failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending Discord message: {e}")
        return False

def check_listings():
    """Check API for listings with revenue share >= 1"""
    try:
        print(f"\n🔍 Checking API at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        
        listings = response.json()
        print(f"📊 Found {len(listings)} total listings")
        
        notified_players = load_notified_players()
        new_notifications = []
        
        for listing in listings:
            try:
                player = listing.get('player', {})
                player_id = player.get('id')
                
                if not player_id:
                    continue
                
                # Get the active contract
                active_contract = player.get('activeContract', {})
                revenue_share = active_contract.get('revenueShare', 0)
                
                # Check if revenue share is 1 or higher
                if revenue_share >= 1:
                    # Skip if already notified
                    if player_id in notified_players:
                        print(f"⏭️  Player {player_id} already notified (RS: {revenue_share}%)")
                        continue
                    
                    # Prepare player info
                    metadata = player.get('metadata', {})
                    player_info = {
                        'name': f"{metadata.get('firstName', '')} {metadata.get('lastName', '')}".strip(),
                        'revenue_share': revenue_share,
                        'overall': metadata.get('overall', 'N/A'),
                        'age': metadata.get('age', 'N/A'),
                        'positions': metadata.get('positions', []),
                        'nationalities': metadata.get('nationalities', []),
                        'price': listing.get('price', 'N/A')
                    }
                    
                    print(f"🎯 Found new player with RS >= 1: {player_info['name']} (ID: {player_id}, RS: {revenue_share}%)")
                    
                    # Send Discord notification
                    if send_discord_message(player_id, player_info):
                        new_notifications.append(player_id)
                        # Small delay between messages to avoid rate limiting
                        time.sleep(1)
            
            except Exception as e:
                print(f"⚠️  Error processing listing: {e}")
                continue
        
        # Update cache with new notifications
        if new_notifications:
            notified_players.update(new_notifications)
            save_notified_players(notified_players)
            print(f"✅ Notified {len(new_notifications)} new player(s)")
        else:
            print("ℹ️  No new players with revenue share >= 1")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main function - checks API every 60 seconds for 4 minutes"""
    print("🚀 MFL Listing Monitor Started")
    print(f"⏰ Will check every 60 seconds for 4 minutes")
    
    # Run 4 times (4 minutes total)
    for i in range(4):
        check_listings()
        
        # Wait 60 seconds before next check (except on last iteration)
        if i < 3:
            print(f"⏳ Waiting 60 seconds... ({i+1}/4 checks complete)")
            time.sleep(60)
    
    print("\n✅ Monitoring session complete")

if __name__ == "__main__":
    main()
