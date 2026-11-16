# Star Wars Galaxies (SWG) Linux & Handheld Launchers

All-in-one Python scripts designed to handle setup, retail ISO extraction, auto-patching, authentication handshakes, and launching for **SWG Uprising** and **SWG Infinity** across SteamOS (Steam Deck) and CachyOS / Arch Linux environments.

---

## Script Directory & Overview

| Script Name | Target Platform | Community / Server | Key Features & Implementation |
| :--- | :--- | :--- | :--- |
| `infinity-CachyOS.py` | CachyOS / Arch Linux | SWG Infinity | • Native `pacman` integration for Wine, Gecko, Mono, and ISO tools (`p7zip`, `unshield`)<br>• NestJS REST API authentication & JWT session tokens<br>• Automated manifest patcher with MD5 verification |
| `infinity-SteamOS.py` | SteamOS / Steam Deck | SWG Infinity | • Immutable filesystem safe<br>• Fetches portable Wine builds and static extraction tools into user space (`~/.local`)<br>• Handles NestJS session authentication & live client file updates |
| `uprising-CachyOS.py` | CachyOS / Arch Linux | SWG Uprising | • Native `pacman` tooling<br>• Wayland / Gamescope resolution safety fallbacks<br>• Custom SOE protocol authentication and UDP packet handshake handling |
| `uprising-SteamOS.py` | SteamOS / Steam Deck | SWG Uprising | • Designed for Steam Deck Game Mode / SteamOS<br>• Portable Wine runtimes & local library provisioning<br>• SOE login packet builder, CRC validator, and custom live-channel patcher |

---

### Usage Instructions
Enable Execution: Right-click the script file, select Properties > Permissions, and check Allow executing file as program.

Open Terminal: Right-click inside the folder containing the script and select Open in Terminal.

Run the Script: Type ./<script_name.py> and press Enter.
---

## Acknowledgments

These scripts were developed and refactored with assistance from **Gemini AI**.
