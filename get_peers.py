# In this file we fetch the IP list of peers from tracker

import urllib.parse
import urllib.request
import hashlib
import os
import random
from parser import bdecode, bencode

def get_peers_from_tracker(torrent_file_path, port=6881, numwant=50):
    """
    Communicate with the tracker to fetch a list of peers for the torrent.
    """
    # Read and decode the torrent file
    with open(torrent_file_path, 'rb') as f:
        torrent_data = f.read()
    decoded = bdecode(torrent_data)
    
    if b'announce' not in decoded:
        raise ValueError("Torrent file missing 'announce' key")
    announce_url = decoded[b'announce'].decode('utf-8')
    
    info = decoded[b'info']
    # Re-encode info to compute info_hash
    info_bencoded = bencode(info)
    info_hash = hashlib.sha1(info_bencoded).digest()
    
    # Calculate total bytes left
    if b'length' in info:
        left = info[b'length']
    elif b'files' in info:
        left = sum(f[b'length'] for f in info[b'files'])
    else:
        raise ValueError("Invalid info dictionary")
    
    # Generate a peer_id
    peer_id = b'-PY0001-' + os.urandom(12)
    
    params = {
        'info_hash': info_hash,
        'peer_id': peer_id,
        'port': port,
        'uploaded': 0,
        'downloaded': 0,
        'left': left,
        'compact': 1,
        'event': 'started',
        'numwant': numwant,
    }
    
    # URL-encode binary values properly
    query_parts = []
    for key, val in params.items():
        if isinstance(val, bytes):
            encoded_val = urllib.parse.quote(val, safe='')
            query_parts.append(f"{key}={encoded_val}")
        else:
            query_parts.append(f"{key}={urllib.parse.quote(str(val), safe='')}")
    
    query_string = '&'.join(query_parts)
    full_url = announce_url + ('&' if '?' in announce_url else '?') + query_string
    
    # Send HTTP GET request
    req = urllib.request.Request(full_url)
    req.add_header('User-Agent', 'Python-BitTorrent-Client/1.0')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            tracker_data = response.read()
    except Exception as e:
        raise ValueError(f"Tracker request failed: {e}")

    # Decode the tracker response
    tracker_decoded = bdecode(tracker_data)
    
    if b'failure reason' in tracker_decoded:
        raise ValueError(f"Tracker failure: {tracker_decoded[b'failure reason'].decode()}")
    
    peers_data = tracker_decoded[b'peers']
    peers = []

    # Compact format handling
    if isinstance(peers_data, bytes):
        for i in range(0, len(peers_data), 6):
            ip = '.'.join(map(str, peers_data[i:i+4]))
            port = int.from_bytes(peers_data[i+4:i+6], 'big')
            peers.append((ip, port))
    # Non-compact format handling
    elif isinstance(peers_data, list):
        for p in peers_data:
            peers.append((p[b'ip'].decode(), p[b'port']))
    
    return peers

# --- SAFAYI WALA OUTPUT ---
if __name__ == "__main__":
    try:
        # File name check karna agar tune badla hai toh
        torrent_name = 'one-piece.torrent' 
        peers = get_peers_from_tracker(torrent_name)
        
        print(f"\n🚀 NovaTorrent Engine")
        print(f"File: {torrent_name}")
        print(f"✅ Found {len(peers)} peers from tracker.")
        print("-" * 40)
        
        # Sirf pehle 10 peers readable format mein dikhao
        for i, (ip, port) in enumerate(peers[:10]):
            print(f"[{i+1}] Peer Address: {ip}:{port}")
            
        if len(peers) > 10:
            print(f"... and {len(peers) - 10} more peers are available.")
            
    except Exception as e:
        print(f"❌ Error: {e}")