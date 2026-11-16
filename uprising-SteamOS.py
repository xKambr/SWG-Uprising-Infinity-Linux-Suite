#!/usr/bin/env python3
"""
SWG Uprising - All-in-One Installer, Patcher & Launcher (SteamOS / CachyOS / Linux)
Replaces: swg_setup.sh, setup_uprising.sh, and launch_uprising.py
"""
import argparse
import getpass
import glob
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import urllib.request
import zlib

# ==============================================================================
# CONSTANTS & ENDPOINTS
# ==============================================================================
SERVER_IP = "135.148.150.69"
SERVER_PORT = 44453
CLIENT_VERSION = "20050408-18:00"
LOGIN_CLIENT_ID = 1091772310
LOGIN_CLIENT_TOKEN = 2863830726
ERROR_MESSAGE = 3047946522

LIVE_CHANNEL_URL = "https://downloads.swguprising.com/live-channel.json"
WINE_PORTABLE_URL = "https://github.com/Kron4ek/Wine-Builds/releases/download/9.0/wine-9.0-staging-amd64.tar.xz"
DXVK_URL = "https://github.com/doitsujin/dxvk/releases/download/v2.3/dxvk-2.3.tar.gz"
SEVENZIP_URL = "https://www.7-zip.org/a/7z2408-linux-x64.tar.xz"
OPENSSL11_URL = "https://archive.archlinux.org/packages/o/openssl-1.1/openssl-1.1-1.1.1.w-1-x86_64.pkg.tar.zst"
UNSHIELD_URL = "https://archive.archlinux.org/packages/u/unshield/unshield-1.5.1-1-x86_64.pkg.tar.zst"

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
}

# ==============================================================================
# 1. ENVIRONMENT & STEAMOS TOOLING PROVISIONER
# ==============================================================================

def is_steamos() -> bool:
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            return "steamos" in f.read().lower()
    return False

def download_file(url: str, dest: str, headers: dict = None):
    req = urllib.request.Request(url, headers=headers or HTTP_HEADERS)
    with urllib.request.urlopen(req, timeout=120.0) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out, length=262144)

def ensure_wine_runner(steamos: bool) -> tuple:
    if steamos:
        runner_dir = os.path.expanduser("~/.local/share/wine-runners")
        runner_ver = "wine-9.0-staging-amd64"
        wine_bin = os.path.join(runner_dir, runner_ver, "bin", "wine")
        wineboot_bin = os.path.join(runner_dir, runner_ver, "bin", "wineboot")
        if not os.path.isfile(wine_bin):
            print(f"==> SteamOS: Downloading portable {runner_ver} into {runner_dir}...")
            os.makedirs(runner_dir, exist_ok=True)
            tar_tmp = f"/tmp/{runner_ver}.tar.xz"
            download_file(WINE_PORTABLE_URL, tar_tmp)
            subprocess.run(["tar", "-xf", tar_tmp, "-C", runner_dir], check=True)
            os.remove(tar_tmp)
        return wine_bin, wineboot_bin

    wine_bin = shutil.which("wine")
    if not wine_bin:
        if shutil.which("pacman"):
            print("==> Installing Wine via pacman...")
            subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm", "wine", "wine-gecko", "wine-mono"], check=True)
            wine_bin = shutil.which("wine")
        else:
            sys.exit("Error: Wine is not installed. Please install Wine and re-run.")
    wineboot_bin = shutil.which("wineboot") or f"{wine_bin}boot"
    return wine_bin, wineboot_bin

def ensure_iso_tools(steamos: bool) -> tuple:
    local_bin = os.path.expanduser("~/.local/bin")
    local_lib = os.path.expanduser("~/.local/lib")
    os.makedirs(local_bin, exist_ok=True)
    os.makedirs(local_lib, exist_ok=True)
    os.environ["PATH"] = f"{local_bin}:{os.environ.get('PATH', '')}"

    sevenzip = next((shutil.which(c) for c in ("7z", "7za", "7zz", os.path.join(local_bin, "7zz")) if shutil.which(c)), None)
    if not sevenzip:
        if steamos:
            print("==> SteamOS: Fetching static 7zz binary to ~/.local/bin...")
            tar_tmp = "/tmp/7z.tar.xz"
            download_file(SEVENZIP_URL, tar_tmp)
            subprocess.run(["tar", "-xf", tar_tmp, "-C", local_bin, "7zz"], check=True)
            os.remove(tar_tmp)
            sevenzip = os.path.join(local_bin, "7zz")
            os.chmod(sevenzip, 0o755)
        elif shutil.which("pacman"):
            subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm", "p7zip"], check=True)
            sevenzip = shutil.which("7z") or shutil.which("7za")
        else:
            sys.exit("Error: 7z / p7zip is required to extract ISOs.")

    if steamos and not os.path.exists(os.path.join(local_lib, "libcrypto.so.1.1")):
        print("==> SteamOS: Fetching libcrypto.so.1.1 into ~/.local/lib...")
        pkg_tmp = "/tmp/openssl11.pkg.tar.zst"
        download_file(OPENSSL11_URL, pkg_tmp)
        subprocess.run(f'"{sevenzip}" x -y -so "{pkg_tmp}" 2>/dev/null | tar -xf - -C /tmp', shell=True, check=True)
        for f in glob.glob("/tmp/usr/lib/libcrypto.so.1.1*"):
            shutil.copy2(f, local_lib)
        shutil.rmtree("/tmp/usr", ignore_errors=True)
        os.remove(pkg_tmp)

    unshield = os.path.join(local_bin, "unshield") if os.path.exists(os.path.join(local_bin, "unshield")) else shutil.which("unshield")
    if not unshield:
        if steamos:
            print("==> SteamOS: Fetching unshield into ~/.local/bin...")
            pkg_tmp = "/tmp/unshield.pkg.tar.zst"
            download_file(UNSHIELD_URL, pkg_tmp)
            subprocess.run(f'"{sevenzip}" x -y -so "{pkg_tmp}" 2>/dev/null | tar -xf - -C /tmp', shell=True, check=True)
            shutil.copy2("/tmp/usr/bin/unshield", os.path.join(local_bin, "unshield"))
            os.chmod(os.path.join(local_bin, "unshield"), 0o755)
            for f in glob.glob("/tmp/usr/lib/libunshield*"):
                shutil.copy2(f, local_lib)
            shutil.rmtree("/tmp/usr", ignore_errors=True)
            os.remove(pkg_tmp)
            unshield = os.path.join(local_bin, "unshield")
        elif shutil.which("pacman"):
            subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm", "unshield"], check=True)
            unshield = shutil.which("unshield")
        else:
            sys.exit("Error: unshield is required to unpack SWG cabinet files.")

    return sevenzip, unshield

# ==============================================================================
# 2. RETAIL ISO EXTRACTION & PREFIX INITIALIZATION
# ==============================================================================

def find_or_prompt_iso(disc_num: int, search_dir: str) -> str:
    for root, _, files in os.walk(search_dir):
        if root[len(search_dir):].count(os.sep) > 2:
            continue
        for f in sorted(files):
            low = f.lower()
            if low.endswith(".iso") and str(disc_num) in low and ("galaxies" in low or "disc" in low or "swg" in low):
                found = os.path.join(root, f)
                print(f"  Found Disc {disc_num}: {found}")
                return found

    while True:
        entered = input(f"Enter path to SWG Retail Disc {disc_num} ISO: ").strip().strip("'\"")
        entered = os.path.expanduser(entered)
        if os.path.isfile(entered):
            return entered
        print(f"  File not found: {entered}")

def extract_retail_isos(client_dir: str, search_dir: str, steamos: bool):
    sevenzip, unshield = ensure_iso_tools(steamos)
    disc1 = find_or_prompt_iso(1, search_dir)
    disc2 = find_or_prompt_iso(2, search_dir)
    disc3 = find_or_prompt_iso(3, search_dir)

    stage_dir = os.path.join(client_dir, ".swg_stage_tmp")
    cabs_dir = os.path.join(stage_dir, "cabs")
    unpacked_dir = os.path.join(stage_dir, "unpacked")
    shutil.rmtree(stage_dir, ignore_errors=True)
    os.makedirs(cabs_dir, exist_ok=True)
    os.makedirs(unpacked_dir, exist_ok=True)

    try:
        print("==> Extracting cabinet archives from ISOs...")
        for iso in (disc1, disc2, disc3):
            subprocess.run(
                [sevenzip, "e", "-y", f"-o{cabs_dir}", iso, "data*.cab", "data*.hdr", "DATA*.CAB", "DATA*.HDR"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        for fname in os.listdir(cabs_dir):
            if fname != fname.lower():
                os.replace(os.path.join(cabs_dir, fname), os.path.join(cabs_dir, fname.lower()))

        print("==> Unpacking .tre files from InstallShield cabinets...")
        env = os.environ.copy()
        local_lib = os.path.expanduser("~/.local/lib")
        env["LD_LIBRARY_PATH"] = f"{local_lib}:{env.get('LD_LIBRARY_PATH', '')}"

        data4 = os.path.join(cabs_dir, "data4.cab")
        data1 = os.path.join(cabs_dir, "data1.hdr")
        if os.path.exists(data4):
            res = subprocess.run([unshield, "-d", unpacked_dir, "-g", "SWG Files", "x", data4], cwd=cabs_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                subprocess.run([unshield, "-d", unpacked_dir, "x", data4], cwd=cabs_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(data1):
            subprocess.run([unshield, "-d", unpacked_dir, "-g", "SWG Files", "x", data1], cwd=cabs_dir, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        count = 0
        for root, _, files in os.walk(unpacked_dir):
            for f in files:
                if f.lower().endswith(".tre"):
                    shutil.move(os.path.join(root, f), os.path.join(client_dir, f.lower()))
                    count += 1
                    print(f"  -> Deployed: {f.lower()}")

        if count == 0:
            sys.exit("Error: No .tre archives were extracted from the provided ISOs.")
        print(f"==> Successfully deployed {count} base retail .tre archives.")
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)

def create_desktop_shortcuts(client_dir: str, script_path: str):
    term_bin = next((t for t in ("konsole", "alacritty", "kitty", "foot", "ptyxis", "gnome-terminal", "xfce4-terminal") if shutil.which(t)), None)
    py_bin = shutil.which("python3") or "python3"
    if not term_bin:
        exec_cmd, term_flag = f'{py_bin} "{script_path}"', "true"
    elif term_bin == "gnome-terminal":
        exec_cmd, term_flag = f'gnome-terminal -- {py_bin} "{script_path}"', "false"
    elif term_bin == "xfce4-terminal":
        exec_cmd, term_flag = f'xfce4-terminal -x {py_bin} "{script_path}"', "false"
    else:
        exec_cmd, term_flag = f'{term_bin} -e {py_bin} "{script_path}"', "false"

    desktop_content = (
        "[Desktop Entry]\n"
        "Name=SWG Uprising\n"
        "Comment=Star Wars Galaxies Uprising\n"
        f"Path={client_dir}\n"
        f"Exec={exec_cmd}\n"
        f"Terminal={term_flag}\n"
        "Type=Application\n"
        "Categories=Game;\n"
    )

    for folder in (os.path.expanduser("~/.local/share/applications"), os.path.expanduser("~/Desktop")):
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, "swg-uprising.desktop")
        with open(target, "w") as f:
            f.write(desktop_content)
        os.chmod(target, 0o755)

def run_initial_setup(script_source_dir: str, force_isos: bool = False) -> str:
    print("==========================================================")
    print("      SWG Uprising - Unified Setup (Arch / SteamOS)       ")
    print("==========================================================")
    steamos = is_steamos()
    wine_bin, wineboot_bin = ensure_wine_runner(steamos)
    print(f"==> Using Wine runner: {wine_bin}")

    default_prefix = os.path.expanduser("~/Games/SWG-Uprising")
    entered = input(f"\nEnter Wine prefix destination path [{default_prefix}]: ").strip()
    prefix = os.path.expanduser(entered) if entered else default_prefix

    user = os.environ.get("USER") or getpass.getuser()
    client_dir = os.path.join(prefix, "drive_c", "users", user, "AppData", "Local", "Uprising", "Client")
    os.makedirs(os.path.join(client_dir, ".uprising", "manifests"), exist_ok=True)

    with open(os.path.join(client_dir, "runner_config.json"), "w") as f:
        json.dump({"wine_bin": wine_bin, "is_steamos": steamos, "wine_prefix": prefix}, f, indent=2)

    print(f"==> Initializing Wine prefix at {prefix}...")
    env = os.environ.copy()
    env["WINEPREFIX"] = prefix
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml="
    subprocess.run([wineboot_bin, "-u"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for dll in ("dinput8", "d3d9"):
        subprocess.run(
            [wine_bin, "reg", "add", r"HKCU\Software\Wine\DllOverrides", "/v", dll, "/d", "native,builtin", "/f"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    print("==> Provisioning DXVK 2.3 (x32)...")
    dxvk_tmp = "/tmp/dxvk.tar.gz"
    download_file(DXVK_URL, dxvk_tmp)
    subprocess.run(["tar", "-xzf", dxvk_tmp, "-C", "/tmp"], check=True)
    for dll in ("d3d9.dll", "dxgi.dll"):
        src = f"/tmp/dxvk-2.3/x32/{dll}"
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(client_dir, dll))
    shutil.rmtree("/tmp/dxvk-2.3", ignore_errors=True)
    os.remove(dxvk_tmp)

    with open(os.path.join(client_dir, "dxvk.conf"), "w") as f:
        f.write("d3d9.forceWindowedMode = true\nd3d9.disableModeSwitch = true\n")

    if not os.path.exists(os.path.join(client_dir, "options.cfg")):
        with open(os.path.join(client_dir, "options.cfg"), "w") as f:
            f.write("[ClientGraphics]\n\twindowed=1\n\tborderlessWindow=1\n\tuseHardwareMouseCursor=1\n")

    has_bottom_tre = os.path.exists(os.path.join(client_dir, "bottom.tre"))
    if force_isos or not has_bottom_tre:
        choice = input("\nExtract base retail .tre files from ISOs now? [Y/n]: ").strip() or "Y"
        if choice.lower().startswith("y"):
            extract_retail_isos(client_dir, script_source_dir, steamos)

    dest_script = os.path.join(client_dir, "uprising.py")
    curr_script = os.path.abspath(__file__)
    if os.path.abspath(curr_script) != os.path.abspath(dest_script):
        shutil.copy2(curr_script, dest_script)
        os.chmod(dest_script, 0o755)

    create_desktop_shortcuts(client_dir, dest_script)
    print(f"==> Setup complete! Installed launcher to: {dest_script}\n")
    return client_dir

# ==============================================================================
# 3. PATCHER & SOE AUTHENTICATION
# ==============================================================================

def check_and_apply_updates(client_dir: str):
    print("Checking for SWG Uprising client updates...")
    req = urllib.request.Request(LIVE_CHANNEL_URL, headers=HTTP_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            channel_data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Warning: Could not check for updates ({e}). Proceeding with local client.")
        return

    remote_release = channel_data.get("releaseId")
    manifest_url = channel_data.get("manifestUrl")
    manifest_sha = channel_data.get("manifestSha256", "")

    state_file = os.path.join(client_dir, ".uprising", "installed-state.json")
    installed_release = None
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                installed_release = json.load(f).get("releaseId")
        except Exception:
            pass

    if installed_release == remote_release:
        print(f"Client is up to date ({remote_release}).")
        return

    print(f"\nUpdate available! Installed: {installed_release} -> Remote: {remote_release}")
    man_req = urllib.request.Request(manifest_url, headers=HTTP_HEADERS)
    with urllib.request.urlopen(man_req, timeout=10.0) as resp:
        manifest = json.loads(resp.read().decode())

    files = manifest.get("files", [])
    total_files = len(files)
    downloaded = 0

    for idx, item in enumerate(files, 1):
        rel_path = item["path"]
        expected_sha = item["sha256"].lower()
        url = item["url"]
        full_path = os.path.join(client_dir, rel_path)

        needs_download = True
        if os.path.exists(full_path):
            hasher = hashlib.sha256()
            with open(full_path, "rb") as fp:
                while chunk := fp.read(65536):
                    hasher.update(chunk)
            if hasher.hexdigest().lower() == expected_sha:
                needs_download = False

        if needs_download:
            print(f"[{idx}/{total_files}] Downloading {rel_path}...")
            os.makedirs(os.path.dirname(full_path) or client_dir, exist_ok=True)
            download_file(url, full_path)
            downloaded += 1

    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w") as f:
        json.dump({"releaseId": remote_release, "manifestSha256": manifest_sha, "clientMode": "phase-b-dinput8"}, f, indent=2)
    print(f"Update complete! ({downloaded} files updated)\n")

def make_crc_table():
    table = [0] * 256
    for i in range(256):
        val = i
        for _ in range(8):
            val = 3988292384 ^ (val >> 1) if (val & 1) else (val >> 1)
        table[i] = val & 0xFFFFFFFF
    return table

CRC_TABLE = make_crc_table()

def generate_soe_crc(data: bytes, seed: int) -> int:
    crc = (CRC_TABLE[(~seed) & 0xFF] ^ 0xFFFFFF) & 0xFFFFFFFF
    for shift in (8, 16, 24):
        idx = ((seed >> shift) ^ crc) & 0xFF
        crc = ((crc >> 8) & 0xFFFFFF) ^ CRC_TABLE[idx]
    for b in data:
        crc = ((crc >> 8) & 0xFFFFFF) ^ CRC_TABLE[(b ^ crc) & 0xFF]
    return (~crc) & 0xFFFFFFFF

def append_crc(packet: bytearray, seed: int):
    crc = generate_soe_crc(packet[:-2], seed)
    struct.pack_into(">H", packet, len(packet) - 2, crc & 0xFFFF)

def validate_crc(packet: bytes, seed: int) -> bool:
    if len(packet) < 2:
        return False
    return struct.unpack(">H", packet[-2:])[0] == (generate_soe_crc(packet[:-2], seed) & 0xFFFF)

def crypt_soe_packet(packet: bytearray, seed: int, decrypt: bool):
    offset = 2 if packet[0] == 0 else 1
    crypt_len = len(packet) - (4 if packet[0] == 0 else 3)
    pos = offset
    for _ in range(crypt_len // 4):
        orig = struct.unpack_from("<I", packet, pos)[0]
        struct.pack_into("<I", packet, pos, (orig ^ seed) & 0xFFFFFFFF)
        seed = orig if decrypt else struct.unpack_from("<I", packet, pos)[0]
        pos += 4
    for _ in range(crypt_len % 4):
        packet[pos] ^= (seed & 0xFF)
        pos += 1

def encode_ascii(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<H", len(raw)) + raw

def build_data_packet(payload: bytes, seed: int, seq: int = 0) -> bytes:
    pkt = bytearray(len(payload) + 7)
    struct.pack_into("<H", pkt, 0, 2304)
    struct.pack_into(">H", pkt, 2, seq)
    pkt[4:4 + len(payload)] = payload
    crypt_soe_packet(pkt, seed, False)
    append_crc(pkt, seed)
    return bytes(pkt)

def build_ack_packet(seq: int, seed: int) -> bytes:
    pkt = bytearray(7)
    struct.pack_into("<H", pkt, 0, 5376)
    struct.pack_into(">H", pkt, 2, seq)
    crypt_soe_packet(pkt, seed, False)
    append_crc(pkt, seed)
    return bytes(pkt)

def read_ascii(msg: bytes, offset: int):
    if offset + 2 > len(msg):
        return "", offset
    length = struct.unpack_from("<H", msg, offset)[0]
    offset += 2
    return msg[offset:offset + length].decode("utf-8", errors="replace"), offset + length

def parse_application(message: bytes):
    if len(message) < 6 or struct.unpack_from("<H", message, 0)[0] != 4:
        return None
    hash_val = struct.unpack_from("<I", message, 2)[0]
    cursor = 6
    if hash_val == ERROR_MESSAGE:
        err_type, cursor = read_ascii(message, cursor)
        err_detail, cursor = read_ascii(message, cursor)
        raise RuntimeError(f"Login Rejected: {err_type} - {err_detail}")
    if hash_val != LOGIN_CLIENT_TOKEN or cursor + 4 > len(message):
        return None
    token_len = struct.unpack_from("<I", message, cursor)[0] - 4
    cursor += 4
    session_id = message[cursor:cursor + token_len].decode("ascii", errors="replace")
    cursor += token_len + 8
    username, _ = read_ascii(message, cursor)
    return {"username": username, "sessionId": session_id}

def split_messages(payload: bytes):
    if len(payload) < 2 or struct.unpack_from("<H", payload, 0)[0] != 6400:
        return [payload]
    results, offset = [], 2
    while offset < len(payload):
        length = payload[offset]
        offset += 1
        if length == 255:
            if offset + 2 > len(payload):
                break
            length = struct.unpack_from(">H", payload, offset)[0]
            offset += 2
        results.append(payload[offset:offset + length])
        offset += length
    return results

def get_screen_resolution() -> tuple:
    try:
        output = subprocess.check_output(["xrandr"], text=True, stderr=subprocess.DEVNULL)
        for line in output.splitlines():
            if "*" in line:
                w, h = line.split()[0].split("x")
                return int(w), int(h)
    except Exception:
        pass
    for mode_file in glob.glob("/sys/class/drm/card*-*/modes"):
        try:
            with open(mode_file, "r") as f:
                first = f.readline().strip()
                if "x" in first:
                    w, h = first.split("x")
                    return int(w), int(h)
        except Exception:
            continue
    return 1280, 800

def main():
    parser = argparse.ArgumentParser(description="SWG Uprising Unified Installer & Launcher")
    parser.add_argument("--setup", action="store_true", help="Run prefix/shortcut/ISO setup wizard")
    parser.add_argument("--extract-isos", action="store_true", help="Re-extract retail SWG ISOs into client folder")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_file = os.path.join(script_dir, "runner_config.json")

    if args.setup or not os.path.exists(cfg_file):
        client_dir = run_initial_setup(script_dir, force_isos=args.extract_isos)
    else:
        client_dir = script_dir
        if args.extract_isos:
            extract_retail_isos(client_dir, script_dir, is_steamos())

    with open(os.path.join(client_dir, "runner_config.json"), "r") as f:
        runner_cfg = json.load(f)

    wine_bin = runner_cfg.get("wine_bin") or shutil.which("wine") or "wine"
    prefix = runner_cfg.get("wine_prefix") or os.path.expanduser("~/Games/SWG-Uprising")

    check_and_apply_updates(client_dir)

    username = input("Username: ").strip()
    if not username:
        sys.exit("Username cannot be empty.")
    password = getpass.getpass("Password: ")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(4.0)
    conn_id = struct.unpack("<I", os.urandom(4))[0]
    req = struct.pack("<H", 256) + struct.pack("<H", 0) + struct.pack(">H", 2) + struct.pack("<I", conn_id) + struct.pack(">I", 496)
    sock.sendto(req, (SERVER_IP, SERVER_PORT))

    resp, _ = sock.recvfrom(2048)
    seed = struct.unpack(">I", resp[6:10])[0]
    cred_payload = struct.pack("<H", 4) + struct.pack("<I", LOGIN_CLIENT_ID) + encode_ascii(username) + encode_ascii(password) + encode_ascii(CLIENT_VERSION)
    sock.sendto(build_data_packet(cred_payload, seed), (SERVER_IP, SERVER_PORT))

    session, fragments, fragment_size = None, [], 0
    while not session:
        packet, _ = sock.recvfrom(2048)
        if not validate_crc(packet, seed):
            continue
        opcode = struct.unpack_from("<H", packet, 0)[0]
        if opcode not in (2304, 3328):
            continue
        pkt_ba = bytearray(packet)
        crypt_soe_packet(pkt_ba, seed, True)
        seq = struct.unpack_from(">H", pkt_ba, 2)[0]
        sock.sendto(build_ack_packet(seq, seed), (SERVER_IP, SERVER_PORT))
        payload = zlib.decompress(bytes(pkt_ba[4:-3])) if pkt_ba[-3] == 1 else bytes(pkt_ba[4:-3])
        if opcode == 3328:
            if not fragments:
                fragment_size = struct.unpack_from(">I", payload, 0)[0]
                payload = payload[4:]
            fragments.append(payload)
            if sum(len(f) for f in fragments) < fragment_size:
                continue
            payload = b"".join(fragments)[:fragment_size]
            fragments = []
        for msg in split_messages(payload):
            if res := parse_application(msg):
                session = res
                break

    width, height = get_screen_resolution()
    game_args = [
        wine_bin, "explorer", f"/desktop=SWG,{width}x{height}", "SWGEmu.exe", "--",
        "-s", "ClientGame", f"loginServerAddress0={SERVER_IP}", f"loginServerPort0={SERVER_PORT}", f"loginClientID={session['username']}",
        "-s", "Station", "subscriptionFeatures=1", "gameFeatures=65535", f"sessionId={session['sessionId']}",
        "-s", "SwgClient", "allowMultipleInstances=true",
        "-s", "ClientGraphics", f"screenWidth={width}", f"screenHeight={height}", "windowed=true", "borderlessWindow=true",
    ]

    env = os.environ.copy()
    env["WINEPREFIX"] = prefix
    subprocess.run(game_args, cwd=client_dir, env=env)

if __name__ == "__main__":
    main()
