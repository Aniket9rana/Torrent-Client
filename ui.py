import asyncio
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
import socket
import struct
import random
import urllib.parse
import hashlib
import time
import sys
import os

from parser import bdecode, bencode
from get_peers import get_peers_from_tracker
from connect_to_peer_async import TorrentDownloader 

# UDP FIX: Helper for UDP Trackers
def get_peers_udp(url, info_hash, peer_id):
    try:
        parsed = urllib.parse.urlparse(url)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        conn_id, trans_id = 0x41727101980, random.randint(0, 2**31 - 1)
        sock.sendto(struct.pack(">QII", conn_id, 0, trans_id), (parsed.hostname, parsed.port))
        res, _ = sock.recvfrom(1024)
        _, _, conn_id = struct.unpack(">IIQ", res[:16])
        sock.sendto(struct.pack(">QII20s20sQQQIIIH", conn_id, 1, trans_id, info_hash, peer_id, 0, 0, 0, 0, 0, 0, -1, 6881), (parsed.hostname, parsed.port))
        res, _ = sock.recvfrom(4096)
        peers = []
        for i in range(20, len(res), 6):
            peers.append((socket.inet_ntoa(res[i:i+4]), struct.unpack(">H", res[i+4:i+6])[0]))
        return peers
    except: return []

class NovaTorrentApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NovaTorrent - Pro Client")
        self.geometry("750x500")
        self.downloader = self.loop = self.torrent_path = None
        self.is_running = False
        
        # Protocol for window closing (X button)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        ctk.set_appearance_mode("Dark")
        self.label = ctk.CTkLabel(self, text="⚡ NOVATORRENT", font=("Orbitron", 28, "bold"), text_color="#3498db")
        self.label.pack(pady=30)
        
        self.card = ctk.CTkFrame(self, corner_radius=15)
        self.card.pack(padx=30, fill="x")
        
        self.file_name_label = ctk.CTkLabel(self.card, text="No Torrent Loaded", font=("Arial", 16, "bold"))
        self.file_name_label.pack(pady=10)
        
        self.status_label = ctk.CTkLabel(self.card, text="Ready", text_color="gray")
        self.status_label.pack(pady=5)
        
        self.prog_label = ctk.CTkLabel(self, text="Progress: 0.00%", font=("Arial", 12))
        self.prog_label.pack(pady=10)
        
        self.progress_bar = ctk.CTkProgressBar(self, width=550, height=15)
        self.progress_bar.set(0)
        self.progress_bar.pack()
        
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=40)
        
        self.upload_btn = ctk.CTkButton(self.btn_frame, text="📁 Select Torrent", command=self.upload_action)
        self.upload_btn.grid(row=0, column=0, padx=10)
        
        self.start_btn = ctk.CTkButton(self.btn_frame, text="▶ Start", fg_color="#2ecc71", state="disabled", command=self.toggle_download)
        self.start_btn.grid(row=0, column=1, padx=10)
        
        self.stop_btn = ctk.CTkButton(self.btn_frame, text="⏹ Stop", fg_color="#e74c3c", state="disabled", command=self.stop_logic)
        self.stop_btn.grid(row=0, column=2, padx=10)

    def upload_action(self):
        p = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent")])
        if p:
            self.torrent_path = p
            with open(p, 'rb') as f: d = bdecode(f.read())
            self.file_name_label.configure(text=f"📦 {d[b'info'][b'name'].decode('utf-8', 'ignore')}")
            self.start_btn.configure(state="normal", text="▶ Start", fg_color="#2ecc71")
            self.status_label.configure(text="Loaded")
            self.progress_bar.set(0)
            self.prog_label.configure(text="Progress: 0.00%")

    def toggle_download(self):
        if not self.is_running:
            self.is_running = True
            self.start_btn.configure(text="⏸ Pause", fg_color="#e67e22")
            self.stop_btn.configure(state="normal")
            self.upload_btn.configure(state="disabled")
            threading.Thread(target=self.run_async_engine, daemon=True).start()
        else:
            self.pause_logic()

    def pause_logic(self):
        self.is_running = False
        if self.downloader:
            self.downloader.is_aborted = True
        self.status_label.configure(text="Status: Paused", text_color="orange")
        self.start_btn.configure(text="▶ Resume", fg_color="#3498db")

    def run_async_engine(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start_download())
        except asyncio.CancelledError:
            pass
        finally:
            if self.loop.is_running():
                self.loop.stop()
            self.loop.close()

    async def start_download(self):
        try:
            self.status_label.configure(text="Status: Loading Tracker...", text_color="yellow")
            
            # --- TERMINAL LOGGING START ---
            print("\n" + "="*50)
            print(f"🚀 NOVATORRENT ENGINE STARTING")
            print(f"[*] Torrent File: {os.path.basename(self.torrent_path)}")
            
            with open(self.torrent_path, 'rb') as f:
                decoded = bdecode(f.read())
            
            info_hash = hashlib.sha1(bencode(decoded[b'info'])).digest()
            peer_id = b'-PY0001-' + hashlib.sha1(str(time.time()).encode()).digest()[:12]
            
            urls = [decoded[b'announce'].decode()]
            if b'announce-list' in decoded:
                for tier in decoded[b'announce-list']: urls.append(tier[0].decode())
            
            print(f"[*] Found {len(urls)} trackers in list. Scanning now...")
            print("-"*50)

            all_peers = set()
            for url in urls:
                if not self.is_running: break
                
                # Terminal par tracker status dikhane ke liye
                print(f"[*] Trying: {url[:60]}...", end=" ", flush=True)
                peers_before = len(all_peers)
                
                try:
                    if url.startswith('udp://'):
                        res = get_peers_udp(url, info_hash, peer_id)
                        all_peers.update(res)
                    elif url.startswith('http'):
                        params = urllib.parse.urlencode({'info_hash': info_hash, 'peer_id': peer_id, 'port': 6881, 'compact': 1})
                        with urllib.request.urlopen(url + "?" + params, timeout=3) as r:
                            d = bdecode(r.read())
                            if b'peers' in d and isinstance(d[b'peers'], bytes):
                                p_data = d[b'peers']
                                for i in range(0, len(p_data), 6):
                                    all_peers.add(('.'.join(map(str, p_data[i:i+4])), int.from_bytes(p_data[i+4:i+6], 'big')))
                    
                    if len(all_peers) > peers_before:
                        print(f"DONE (+{len(all_peers) - peers_before} peers)")
                    else:
                        print("NO PEERS")
                except:
                    print("FAILED/TIMEOUT")
            
            print("-" * 50)
            if not all_peers and self.is_running:
                print("[!] Result: No active peers found on any tracker.")
                self.status_label.configure(text="Error: No Peers Found!", text_color="red")
                self.is_running = False
                self.upload_btn.configure(state="normal")
                return

            print(f"[*] Total unique peers collected: {len(all_peers)}")
            target_name = decoded[b'info'][b'name'].decode('utf-8', 'ignore')
            
            self.downloader = TorrentDownloader(self.torrent_path, list(all_peers), max_peers=30)
            
            def up(p, s="0 KB/s"):
                self.progress_bar.set(p)
                self.prog_label.configure(text=f"Progress: {p*100:.2f}% | Speed: {s}")

            # Initial Progress Load
            up(len(self.downloader.verified_indices)/self.downloader.num_pieces)
            
            print(f"[*] Starting piece download workers...")
            self.status_label.configure(text=f"Downloading from {len(all_peers)} peers...", text_color="#3498db")
            
            success = await self.downloader.download(target_name, progress_callback=up)
            
            if success:
                print(f"\n✅ DOWNLOAD COMPLETE: {target_name}")
                self.status_label.configure(text="Status: Completed! 🎉", text_color="#2ecc71")
                messagebox.showinfo("NovaTorrent", "Download Finished!")

        except Exception as e:
            print(f"\n[!] UI ENGINE ERROR: {e}")
            self.status_label.configure(text=f"Error: {str(e)}", text_color="red")
            self.is_running = False

    def stop_logic(self):
        """Download ko rokne aur UI reset karne ke liye"""
        print("\n[*] Stopping download and resetting engine...")
        
        self.is_running = False
        if self.downloader:
            self.downloader.is_aborted = True
        
        # Reset UI elements
        self.status_label.configure(text="Status: Stopped & Reset", text_color="red")
        self.start_btn.configure(text="▶ Start", fg_color="#2ecc71", state="normal")
        self.stop_btn.configure(state="disabled")
        self.upload_btn.configure(state="normal")
        
    def on_closing(self):
        """Puri app band karne ke liye"""
        if messagebox.askokcancel("Quit", "Do you want to exit NovaTorrent?"):
            if self.downloader:
                self.downloader.is_aborted = True
            self.destroy()
            os._exit(0) # Hard exit only when closing the window

if __name__ == "__main__":
    app = NovaTorrentApp()
    app.mainloop()