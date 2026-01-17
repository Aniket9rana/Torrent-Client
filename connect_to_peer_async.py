import asyncio
import socket
import struct
import hashlib
import time
import os  # FIX: name 'os' is not defined
from parser import bdecode, bencode
from collections import defaultdict

class AsyncBitTorrentPeer:
    def __init__(self, ip, port, info_hash, peer_id, timeout=10):
        self.ip, self.port, self.info_hash, self.peer_id = ip, port, info_hash, peer_id
        self.timeout = timeout
        self.reader = self.writer = self.bitfield = None
        self.peer_choking = True
        self.interested = False

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.ip, self.port), timeout=self.timeout)
            return True
        except: return False

    async def handshake(self):
        msg = struct.pack("B", 19) + b"BitTorrent protocol" + b'\x00'*8 + self.info_hash + self.peer_id
        try:
            self.writer.write(msg)
            await self.writer.drain()
            res = await asyncio.wait_for(self.reader.readexactly(68), timeout=self.timeout)
            return res[28:48] == self.info_hash
        except: return False

    async def send_interested(self):
        self.writer.write(struct.pack(">IB", 1, 2))
        await self.writer.drain()
        self.interested = True

    async def send_request(self, index, begin, length):
        self.writer.write(struct.pack(">IBIII", 13, 6, index, begin, length))
        await self.writer.drain()

    async def receive_message(self):
        try:
            length_data = await asyncio.wait_for(self.reader.readexactly(4), timeout=self.timeout)
            length = struct.unpack(">I", length_data)[0]
            if length == 0: return None, None
            msg_data = await asyncio.wait_for(self.reader.readexactly(length), timeout=self.timeout)
            return msg_data[0], msg_data[1:]
        except: return None, None

    def handle_message(self, msg_id, payload):
        if msg_id == 0: self.peer_choking = True
        elif msg_id == 1: self.peer_choking = False
        elif msg_id == 5: self.bitfield = payload
        elif msg_id == 7:
            return ('piece', struct.unpack(">I", payload[0:4])[0], struct.unpack(">I", payload[4:8])[0], payload[8:])
        return None

    def has_piece(self, index):
        if not self.bitfield: return False
        byte_idx, bit_idx = index // 8, 7 - (index % 8)
        return byte_idx < len(self.bitfield) and bool((self.bitfield[byte_idx] >> bit_idx) & 1)

    async def close(self):
        if self.writer: self.writer.close()

async def download_piece_from_peer(peer, piece_index, piece_length, block_size=16384):
    if not peer.interested: await peer.send_interested()
    wait_t = 0
    while peer.peer_choking and wait_t < 5:
        mid, pld = await peer.receive_message()
        peer.handle_message(mid, pld)
        await asyncio.sleep(0.1); wait_t += 0.1
    if peer.peer_choking: return None
    for b in range(0, piece_length, block_size):
        await peer.send_request(piece_index, b, min(block_size, piece_length - b))
    data, blocks_count = {}, (piece_length + block_size - 1) // block_size
    for _ in range(blocks_count * 2):
        mid, pld = await peer.receive_message()
        res = peer.handle_message(mid, pld)
        if res and res[0] == 'piece' and res[1] == piece_index:
            data[res[2]] = res[3]
            if len(data) == blocks_count: return data
    return None

class TorrentDownloader:
    def __init__(self, torrent_file_path, peers, max_peers=5):
        self.torrent_file_path = torrent_file_path
        self.peers = peers
        self.max_peers = max_peers
        self.is_aborted = False
        self.state_file = torrent_file_path + ".state"
        
        with open(torrent_file_path, 'rb') as f:
            torrent_data = bdecode(f.read())
        
        self.info = torrent_data[b'info']
        self.info_hash = hashlib.sha1(bencode(self.info)).digest()
        self.piece_length = self.info[b'piece length']
        self.pieces_hash = self.info[b'pieces']
        self.num_pieces = len(self.pieces_hash) // 20
        
        # Calculate Total Length
        if b'length' in self.info:
            self.total_length = self.info[b'length']
        else:
            self.total_length = sum(f[b'length'] for f in self.info[b'files'])
        
        # Unique Peer ID
        self.peer_id = b'-PY0001-' + hashlib.sha1(str(time.time()).encode()).digest()[:12]
        
        # Data Management
        self.downloaded_pieces = self.load_data_from_disk()
        self.verified_indices = set(self.downloaded_pieces.keys()) 
        self.piece_locks = {i: asyncio.Lock() for i in range(self.num_pieces)}
        self.pieces_in_progress = set()
        
        self.total_downloaded_session = 0
        self.current_speed = 0

        print(f"\n🚀 NovaTorrent Engine Started")
        print(f"[*] Torrent: {os.path.basename(torrent_file_path)}")
        print(f"[*] Total Pieces: {self.num_pieces}")
        print(f"[*] Resume State: {len(self.verified_indices)} pieces already on disk.\n", flush=True)

    def load_data_from_disk(self):
        data = {}
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'rb') as f:
                    while True:
                        h = f.read(8)
                        if not h: break
                        idx, l = struct.unpack(">II", h)
                        data[idx] = f.read(l)
            except: pass
        return data

    def save_piece_to_disk(self, index, data):
        with open(self.state_file, 'ab') as f:
            f.write(struct.pack(">II", index, len(data)) + data)

    def verify_piece(self, idx, data):
        return hashlib.sha1(data).digest() == self.pieces_hash[idx*20:(idx+1)*20]

    async def calculate_speed(self):
        while not self.is_aborted:
            b = self.total_downloaded_session
            await asyncio.sleep(1)
            self.current_speed = self.total_downloaded_session - b

    async def peer_worker(self, ip, port, progress_callback):
        if self.is_aborted: return
        
        print(f"[*] Connecting to {ip}:{port}...", flush=True)
        peer = AsyncBitTorrentPeer(ip, port, self.info_hash, self.peer_id)
        
        if not await peer.connect(): return
        if not await peer.handshake(): 
            await peer.close()
            return
        
        print(f"[+] Handshake Successful: {ip}:{port}", flush=True)
        await peer.send_interested()

        try:
            while len(self.verified_indices) < self.num_pieces and not self.is_aborted:
                msg_id, payload = await peer.receive_message()
                if msg_id is not None: peer.handle_message(msg_id, payload)
                
                if peer.peer_choking: 
                    await asyncio.sleep(0.5)
                    continue
                
                piece_idx = None
                rem = self.num_pieces - len(self.verified_indices)
                
                for i in range(self.num_pieces):
                    if i not in self.verified_indices and peer.has_piece(i):
                        if rem <= 2: piece_idx = i; break
                        async with self.piece_locks[i]:
                            if i not in self.pieces_in_progress:
                                self.pieces_in_progress.add(i); piece_idx = i; break
                
                if piece_idx is None:
                    await asyncio.sleep(1)
                    continue
                
                # Terminal Log for Piece Request
                print(f"[-] Requesting Piece {piece_idx} from {ip}:{port}...", flush=True)
                
                d = await download_piece_from_peer(peer, piece_idx, self.get_piece_length(piece_idx))
                if d:
                    full = b''.join(d[o] for o in sorted(d.keys()))
                    if self.verify_piece(piece_idx, full) and piece_idx not in self.verified_indices:
                        self.downloaded_pieces[piece_idx] = full
                        self.verified_indices.add(piece_idx)
                        self.save_piece_to_disk(piece_idx, full)
                        self.total_downloaded_session += len(full)
                        
                        # Terminal Log for Verification
                        progress = (len(self.verified_indices)/self.num_pieces)*100
                        print(f"✅ Piece {piece_idx} Verified! | Total Progress: {progress:.2f}%", flush=True)
                        
                        if progress_callback: 
                            kb = self.current_speed / 1024
                            s_str = f"{kb/1024:.2f} MB/s" if kb > 1024 else f"{kb:.2f} KB/s"
                            progress_callback(len(self.verified_indices)/self.num_pieces, s_str)
                
                if rem > 2:
                    async with self.piece_locks[piece_idx]: self.pieces_in_progress.discard(piece_idx)
        finally: 
            await peer.close()

    def get_piece_length(self, idx):
        return self.total_length - (idx * self.piece_length) if idx == self.num_pieces - 1 else self.piece_length

    async def download(self, output_file, progress_callback=None):
        stask = asyncio.create_task(self.calculate_speed())
        tasks = [asyncio.create_task(self.peer_worker(ip, port, progress_callback)) for ip, port in self.peers[:self.max_peers]]
        
        try:
            while len(self.verified_indices) < self.num_pieces and not self.is_aborted: 
                await asyncio.sleep(1)
        finally:
            self.is_aborted = True
            stask.cancel()
            for t in tasks: t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            
        if len(self.verified_indices) == self.num_pieces:
            print("\n🎉 ALL PIECES DOWNLOADED! Finalizing file...", flush=True)
            with open(output_file, 'wb') as f:
                for i in range(self.num_pieces): f.write(self.downloaded_pieces[i])
            if os.path.exists(self.state_file): os.remove(self.state_file)
            print(f"✅ File Saved: {output_file}\n", flush=True)
            return True
        return False

async def download_from_peers_async(torrent_file, peers, output_file, max_peers=5, progress_callback=None):
    print(f"\n[*] Initializing Engine for: {output_file}")
    print(f"[*] Target Peers: {len(peers)}")
    
    downloader = TorrentDownloader(torrent_file, peers, max_peers)
    return await downloader.download(output_file, progress_callback)