# 📦 NovaTorrent – Python BitTorrent Client

**NovaTorrent** is a lightweight, high-performance **BitTorrent client** built entirely in **Python** using the **asyncio** framework.  
It is designed to efficiently manage peer-to-peer downloads and communication with a modern interface and robust download control.

---

## 🧠 Overview

BitTorrent is a decentralized peer-to-peer (P2P) file-sharing protocol where files are split into pieces and distributed across many peers instead of downloaded from a single server. This project implements the core features of a BitTorrent client to connect to peers and download data using the BitTorrent protocol. :contentReference[oaicite:0]{index=0}

**NovaTorrent** aims to be a simple educational client while providing real-world torrent download functionality.

---

## 🚀 Features

✔️ Reads and parses `.torrent` files  
✔️ Connects to BitTorrent peers  
✔️ Downloads file pieces concurrently  
✔️ Async I/O powered with Python’s `asyncio`  
✔️ Simple UI interface  
✔️ Modular code for networking and torrent parsing

---

## 📁 Repository Structure


- **main.py** — Entry point for the torrent client  
- **parser.py** — Handles torrent file parsing  
- **ui.py** — Simple interface module  
- **get_peers.py** — Tracker and peer discovery logic  
- **connect_to_peer_async.py** — Asynchronous peer connections  
- **calc_hash.py** — Hashing utilities for verifying downloaded data  
- **spec files** — Specification/design documentation

---

## 📌 How It Works

1. **Torrent Parsing** — Parses `.torrent` metadata and extracts tracker info, file info, and hashes.  
2. **Tracker Communication** — Connects to the announce URL and receives peer lists.  
3. **Peer Connections** — Uses Python’s asynchronous networking to connect to peers and request pieces.  
4. **Download Management** — Downloads file segments from multiple peers and reconstructs the file.

This design follows typical BitTorrent client architecture where files are segmented and exchanged directly between participating peers. :contentReference[oaicite:1]{index=1}

---

## 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| **Python** | Main language for implementation |
| **asyncio** | Asynchronous networking and concurrency |
| **socket** | Low-level peer communication |
| **BitTorrent Protocol** | P2P file sharing protocol standards |
| **Custom UI** | For basic user interaction |

---

## 🧩 Installation & Usage

1. **Clone the repository**
   ```bash
   git clone https://github.com/Aniket9rana/Torrent-Client.git
   cd Torrent-Client

