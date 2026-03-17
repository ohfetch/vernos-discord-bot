import os
import sys
import json
from urllib import request, error
from urllib.parse import urlencode

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

# If python-dotenv isn't available, try to read .env in the project root ourselves
if not load_dotenv:
    # Try to find a .env file in cwd or immediate subfolders
    envpath = None
    for root, dirs, files in os.walk(os.getcwd()):
        if '.env' in files:
            envpath = os.path.join(root, '.env')
            break

    if envpath and os.path.exists(envpath):
        print(f"Loading .env from: {envpath}")
        with open(envpath, 'r', encoding='utf-8') as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln or ln.startswith('#') or '=' not in ln:
                    continue
                k, v = ln.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.getenv("DISCORD_TOKEN")
PREFERRED = os.getenv("QUEUE_LOG_CHANNEL", "logs").lower()
HEADER = '📌 QUEUE STATUS'

if not TOKEN:
    print("Missing DISCORD_TOKEN in environment (.env). Aborting.")
    sys.exit(2)

BASE = "https://discord.com/api/v10"
HEADERS = {"Authorization": f"Bot {TOKEN}", "User-Agent": "Heist-Verify-Script/1.0"}

def get(path):
    req = request.Request(BASE + path, headers=HEADERS)
    try:
        with request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            return json.loads(data)
    except error.HTTPError as e:
        print(f"HTTP error GET {path}: {e.code} {e.reason}")
        try:
            print(e.read().decode())
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"Error GET {path}: {e}")
        return None

me = get('/users/@me')
if not me:
    print('Failed to fetch bot user; aborting.')
    sys.exit(2)
bot_id = me.get('id')
print(f"Bot ID: {bot_id}")

guilds = get('/users/@me/guilds') or []
if not guilds:
    print('No guilds found for bot.')

overall_ok = True

for g in guilds:
    guild_id = g.get('id')
    print('\nGuild:', g.get('name'), guild_id)
    channels = get(f'/guilds/{guild_id}/channels') or []
    preferred_chan = None
    for ch in channels:
        if ch.get('type') != 0:  # text channels only
            continue
        if ch.get('name', '').lower() == PREFERRED:
            preferred_chan = ch
            break

    channels_with_status = []
    for ch in channels:
        if ch.get('type') != 0:
            continue
        ch_id = ch.get('id')
        pins = get(f'/channels/{ch_id}/pins')
        if not pins:
            continue
        for msg in pins:
            author = msg.get('author', {})
            content = msg.get('content', '')
            if author.get('id') == bot_id and content.startswith(HEADER):
                channels_with_status.append((ch.get('name'), ch_id))
                break

    print('Preferred logs channel:', preferred_chan.get('name') if preferred_chan else '(not found)')
    if not channels_with_status:
        print('No queue status pinned messages found in this guild.')
        continue

    print('Channels with pinned queue status:')
    for name, cid in channels_with_status:
        print(' -', name, cid)

    # Verify only preferred channel has them
    if preferred_chan:
        other = [c for c in channels_with_status if c[1] != preferred_chan.get('id')]
        if other:
            overall_ok = False
            print('\nVerification FAILED: Found status in other channels:')
            for name, cid in other:
                print(' *', name, cid)
        else:
            print('\nVerification OK: only in preferred channel')
    else:
        overall_ok = False
        print('\nVerification FAILED: preferred channel not found; statuses exist elsewhere')

if overall_ok:
    print('\nALL CHECKS PASSED: queue status messages are only in the preferred logs channels.')
    sys.exit(0)
else:
    print('\nSOME CHECKS FAILED: see above.')
    sys.exit(1)
