import asyncio
import tkinter as tk
from tkinter import filedialog
from parser import bencode
from parser import bdecode
from get_peers import get_peers_from_tracker
from connect_to_peer_async import download_from_peers_async

def select_torrent_file():
    # File picker window open hogi
    root = tk.Tk()
    root.withdraw() # Main window chhupane ke liye
    file_path = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent")])
    return file_path

async def main():
    # 1. User se file select karwana
    torrent_path = select_torrent_file()
    if not torrent_path:
        print("No file selected. Exiting...")
        return

    # 2. Torrent file parse karke metadata nikaalna
    with open(torrent_path, 'rb') as f:
        torrent_data = bdecode(f.read())
    
    # Torrent ke andar jo asli file ka naam hai wo nikaalna
    original_file_name = torrent_data[b'info'][b'name'].decode()
    print(f"Target File: {original_file_name}")

    # 3. Get peers
    peers = get_peers_from_tracker(torrent_path)
    if len(peers) == 0:
        print("No peers found in tracker. Exiting...")
        return
    
    # 4. Connect with peers and start downloading
    # Ab 'downloaded_file.mkv' ki jagah original_file_name use hoga
    success = await download_from_peers_async(
        torrent_path,
        peers,
        original_file_name,
        max_peers=50
    )
    
    if success:
        print(f"Download successful! Saved as: {original_file_name}")
    else:
        print("Download failed or incomplete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDownload interrupted by user")