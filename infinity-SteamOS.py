#!/usr/bin/env python3
"""
SWG Infinity - All-in-One Installer, Patcher & Launcher (SteamOS / CachyOS / Linux)
Replaces: swgInfinity_setup.sh, setup_infinity.sh, and launch_infinity.py
"""
import argparse
import base64
import getpass
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

# ==============================================================================
# CONSTANTS & ENDPOINTS
# ==============================================================================
MANIFEST_URL = "https://updater.swginfinity.com/manifest.json"
API_BASE_URL = "https://api2.swginfinity.com/api/v2"
DEFAULT_SERVER_CHANNEL = "live"
DEFAULT_HOST = "game.swginfinity.com"
DEFAULT_PORT = 14453

WINE_PORTABLE_URL = "https://github.com/Kron4ek/Wine-Builds/releases/download/9.0/wine-9.0-staging-amd64.tar.xz"
SEVENZIP_URL = "https://www.7-zip.org/a/7z2408-linux-x64.tar.xz"
OPENSSL11_URL = "https://archive.archlinux.org/packages/o/openssl-1.1/openssl-1.1-1.1.1.w-1-x86_64.pkg.tar.zst"
UNSHIELD_URL = "https://archive.archlinux.org/packages/u/unshield/unshield-1.5.1-1-x86_64.pkg.tar.zst"

UPDATER_HEADERS = {
    "User-Agent": "InfinityLauncher/1.0",
    "Accept": "*/*",
}

RETAIL_TRE_ORDER = [
    ("00_00", "bottom.tre"),
    ("00_01", "data_other_00.tre"),
    ("00_02", "data_static_mesh_00.tre"),
    ("00_03", "data_static_mesh_01.tre"),
    ("00_04", "data_texture_00.tre"),
    ("00_05", "data_texture_01.tre"),
    ("00_06", "data_texture_02.tre"),
    ("00_07", "data_texture_03.tre"),
    ("00_08", "data_texture_04.tre"),
    ("00_09", "data_texture_05.tre"),
    ("00_10", "data_texture_06.tre"),
    ("00_11", "data_texture_07.tre"),
    ("00_12", "data_skeletal_mesh_00.tre"),
    ("00_13", "data_skeletal_mesh_01.tre"),
    ("00_14", "data_animation_00.tre"),
    ("00_15", "data_sample_00.tre"),
    ("00_16", "data_sample_01.tre"),
    ("00_17", "data_sample_02.tre"),
    ("00_18", "data_sample_03.tre"),
    ("00_19", "data_sample_04.tre"),
    ("00_20", "data_music_00.tre"),
    ("00_21", "patch_00.tre"),
    ("00_22", "patch_01.tre"),
    ("00_23", "patch_02.tre"),
    ("00_24", "patch_03.tre"),
    ("00_25", "patch_04.tre"),
    ("00_26", "patch_05.tre"),
    ("00_27", "patch_06.tre"),
    ("00_28", "patch_07.tre"),
    ("00_29", "patch_08.tre"),
    ("01_29", "patch_09.tre"),
    ("02_29", "patch_10.tre"),
    ("03_29", "data_sku1_00.tre"),
    ("04_29", "data_sku1_01.tre"),
    ("05_29", "data_sku1_02.tre"),
    ("06_29", "data_sku1_03.tre"),
    ("07_29", "data_sku1_04.tre"),
    ("08_29", "data_sku1_05.tre"),
    ("09_29", "patch_11_00.tre"),
    ("10_29", "data_sku1_06.tre"),
    ("11_29", "patch_11_01.tre"),
    ("12_29", "data_sku1_07.tre"),
    ("13_29", "patch_11_02.tre"),
    ("14_29", "patch_11_03.tre"),
    ("15_29", "patch_12_00.tre"),
    ("16_29", "patch_13_00.tre"),
    ("17_29", "patch_14_00.tre"),
    ("18_29", "default_patch.tre"),
]

# ==============================================================================
# 1. ENVIRONMENT & STEAMOS TOOLING PROVISIONER
# ==============================================================================

def is_steamos() -> bool:
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            return "steamos" in f.read().lower()
    return False

def download_file(url: str, dest: str, headers: dict = None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
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

    # 1. Resolve 7-Zip
    sevenzip = None
    for candidate in ("7z", "7za", "7zz", os.path.join(local_bin, "7zz")):
        if shutil.which(candidate):
            sevenzip = shutil.which(candidate)
            break

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

    # 2. Resolve unshield (+ libcrypto.so.1.1 on SteamOS)
    if steamos:
        libcrypto = os.path.join(local_lib, "libcrypto.so.1.1")
        if not os.path.exists(libcrypto):
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
        # Limit depth to 2
        rel_depth = root[len(search_dir):].count(os.sep)
        if rel_depth > 2:
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
                    src = os.path.join(root, f)
                    dst = os.path.join(client_dir, f.lower())
                    shutil.move(src, dst)
                    count += 1
                    print(f"  -> Deployed: {f.lower()}")

        if count == 0:
            sys.exit("Error: No .tre archives were extracted from the provided ISOs.")
        print(f"==> Successfully deployed {count} base retail .tre archives.")
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)

def create_desktop_shortcuts(client_dir: str, script_path: str):
    term_bin = None
    for t in ("konsole", "alacritty", "kitty", "foot", "ptyxis", "gnome-terminal", "xfce4-terminal"):
        if shutil.which(t):
            term_bin = t
            break

    py_bin = shutil.which("python3") or "python3"
    if not term_bin:
        exec_cmd = f'{py_bin} "{script_path}"'
        term_flag = "true"
    elif term_bin == "gnome-terminal":
        exec_cmd = f'gnome-terminal -- {py_bin} "{script_path}"'
        term_flag = "false"
    elif term_bin == "xfce4-terminal":
        exec_cmd = f'xfce4-terminal -x {py_bin} "{script_path}"'
        term_flag = "false"
    else:
        exec_cmd = f'{term_bin} -e {py_bin} "{script_path}"'
        term_flag = "false"

    desktop_content = (
        "[Desktop Entry]\n"
        "Name=SWG Infinity\n"
        "Comment=Star Wars Galaxies Infinity\n"
        f"Path={client_dir}\n"
        f"Exec={exec_cmd}\n"
        f"Terminal={term_flag}\n"
        "Type=Application\n"
        "Categories=Game;\n"
    )

    app_dir = os.path.expanduser("~/.local/share/applications")
    desk_dir = os.path.expanduser("~/Desktop")
    os.makedirs(app_dir, exist_ok=True)
    os.makedirs(desk_dir, exist_ok=True)

    for target in (os.path.join(app_dir, "swg-infinity.desktop"), os.path.join(desk_dir, "swg-infinity.desktop")):
        with open(target, "w") as f:
            f.write(desktop_content)
        os.chmod(target, 0o755)

def run_initial_setup(script_source_dir: str, force_isos: bool = False) -> str:
    print("==========================================================")
    print("      SWG Infinity - Unified Setup (Arch / SteamOS)       ")
    print("==========================================================")
    steamos = is_steamos()
    wine_bin, wineboot_bin = ensure_wine_runner(steamos)
    print(f"==> Using Wine runner: {wine_bin}")

    default_prefix = os.path.expanduser("~/Games/SWG-Infinity")
    entered = input(f"\nEnter Wine prefix destination path [{default_prefix}]: ").strip()
    prefix = os.path.expanduser(entered) if entered else default_prefix

    user = os.environ.get("USER") or getpass.getuser()
    client_dir = os.path.join(prefix, "drive_c", "users", user, "AppData", "Local", "Infinity", "Client")
    os.makedirs(os.path.join(client_dir, ".infinity"), exist_ok=True)

    with open(os.path.join(client_dir, "runner_config.json"), "w") as f:
        json.dump({"wine_bin": wine_bin, "is_steamos": steamos, "wine_prefix": prefix}, f, indent=2)

    print(f"==> Initializing Wine prefix at {prefix}...")
    env = os.environ.copy()
    env["WINEPREFIX"] = prefix
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml="
    subprocess.run([wineboot_bin, "-u"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("==> Setting native DLL overrides (dinput8, d3d9)...")
    for dll in ("dinput8", "d3d9"):
        subprocess.run(
            [wine_bin, "reg", "add", r"HKCU\Software\Wine\DllOverrides", "/v", dll, "/d", "native,builtin", "/f"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

    with open(os.path.join(client_dir, "dxvk.conf"), "w") as f:
        f.write("d3d9.forceWindowedMode = true\nd3d9.disableModeSwitch = true\n")

    has_bottom_tre = os.path.exists(os.path.join(client_dir, "bottom.tre"))
    if force_isos or not has_bottom_tre:
        choice = input("\nExtract base retail .tre files from ISOs now? [Y/n]: ").strip() or "Y"
        if choice.lower().startswith("y"):
            extract_retail_isos(client_dir, script_source_dir, steamos)

    dest_script = os.path.join(client_dir, "infinity.py")
    curr_script = os.path.abspath(__file__)
    if os.path.abspath(curr_script) != os.path.abspath(dest_script):
        shutil.copy2(curr_script, dest_script)
        os.chmod(dest_script, 0o755)

    create_desktop_shortcuts(client_dir, dest_script)
    print(f"==> Setup complete! Installed launcher to: {dest_script}\n")
    return client_dir

# ==============================================================================
# 3. PATCHER, CONFIG GENERATOR & NESTJS AUTHENTICATION
# ==============================================================================

def compute_md5(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as fp:
        while chunk := fp.read(131072):
            hasher.update(chunk)
    return hasher.hexdigest().lower()

def check_and_apply_updates(client_dir: str):
    print("Checking for SWG Infinity client updates...")
    req = urllib.request.Request(MANIFEST_URL, headers=UPDATER_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            manifest = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Warning: Could not reach manifest server ({e}). Proceeding with local files.")
        return

    files = manifest.get("required", [])
    total_files = len(files)
    downloaded = 0

    for idx, item in enumerate(files, 1):
        rel_path = item["name"].replace("\\", "/")
        expected_md5 = item.get("md5", "").lower()
        expected_size = int(item.get("size", 0))
        url = item["url"]
        full_path = os.path.join(client_dir, rel_path)

        needs_download = True
        if os.path.exists(full_path):
            try:
                if expected_size and os.path.getsize(full_path) == expected_size:
                    if not expected_md5 or compute_md5(full_path) == expected_md5:
                        needs_download = False
            except Exception:
                needs_download = True

        if needs_download:
            size_mb = expected_size / (1024 * 1024)
            print(f"[{idx}/{total_files}] Downloading {rel_path} ({size_mb:.2f} MB)...")
            os.makedirs(os.path.dirname(full_path) or client_dir, exist_ok=True)
            tmp_path = full_path + ".part"
            download_file(url, tmp_path, headers=UPDATER_HEADERS)
            if expected_md5 and compute_md5(tmp_path) != expected_md5:
                os.remove(tmp_path)
                raise RuntimeError(f"MD5 mismatch on {rel_path}")
            os.replace(tmp_path, full_path)
            downloaded += 1

    with open(os.path.join(client_dir, ".manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print("Client is up to date." if downloaded == 0 else f"Update complete! ({downloaded} files updated)\n")

def ensure_config_files(client_dir: str, host: str, port: int, width: int, height: int):
    lower_shader = os.path.join(client_dir, "mtg_patch_009_shader_01.tre")
    upper_shader = os.path.join(client_dir, "mtg_patch_009_Shader_01.tre")
    if os.path.exists(lower_shader) and not os.path.exists(upper_shader):
        try:
            os.symlink("mtg_patch_009_shader_01.tre", upper_shader)
        except Exception:
            pass

    with open(os.path.join(client_dir, "swgemu_login.cfg"), "w", newline="\r\n") as f:
        f.write(f"[ClientGame]\nloginServerAddress0={host}\nloginServerPort0={port}\nfreeChaseCameraMaximumZoom=5\n")

    existing_files = {f.lower(): f for f in os.listdir(client_dir)}
    preload_lines = ["[SharedFile]"]
    for prio, tre_name in RETAIL_TRE_ORDER:
        if tre_name.lower() in existing_files:
            preload_lines.append(f"\tsearchTree_{prio}={existing_files[tre_name.lower()]}")
    with open(os.path.join(client_dir, "swgemu_preload.cfg"), "w", newline="\r\n") as f:
        f.write("\n".join(preload_lines) + "\n")

    options_cfg = os.path.join(client_dir, "options.cfg")
    if not os.path.exists(options_cfg):
        with open(options_cfg, "w", newline="\r\n") as f:
            f.write(f"[ClientGraphics]\n\tscreenWidth={width}\n\tscreenHeight={height}\n\twindowed=1\n\tborderlessWindow=1\n\tuseHardwareMouseCursor=1\n")

    user_inf_cfg = os.path.join(client_dir, "user_infinity.cfg")
    if not os.path.exists(user_inf_cfg):
        with open(user_inf_cfg, "w", newline="\r\n") as f:
            f.write("[SwgClientUserInterface]\n\tchatTabFix=1\n\tchatHideCityChannel=1\n")

    user_cfg = os.path.join(client_dir, "user.cfg")
    if not os.path.exists(user_cfg):
        with open(user_cfg, "w", newline="\r\n") as f:
            f.write("\n")

    with open(os.path.join(client_dir, "swgemu.cfg"), "w", newline="\r\n") as f:
        f.write(
            '.include "swgemu_login.cfg"\n'
            '.include "swgemu_live.cfg"\n'
            '.include "swgemu_preload.cfg"\n'
            '.include "options.cfg"\n'
            '.include "user_infinity.cfg"\n'
            '.include "user.cfg"\n'
        )

def decode_jwt_payload(token: str) -> dict:
    try:
        parts = token.split(".")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        return {}

def api_request(method: str, path: str, body: dict = None, access_token: str = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Client-Source": "launcher",
        "User-Agent": "InfinityLauncher/1.0",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{API_BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}

def authenticate_and_create_session(client_dir: str) -> dict:
    auth_file = os.path.join(client_dir, ".infinity", "auth.json")
    saved = {}
    if os.path.exists(auth_file):
        try:
            with open(auth_file, "r") as f:
                saved = json.load(f)
        except Exception:
            pass

    access_token = saved.get("accessToken")
    refresh_token = saved.get("refreshToken")
    username = saved.get("username")
    user_id = saved.get("userId")

    if refresh_token:
        try:
            jwt_data = decode_jwt_payload(access_token) if access_token else {}
            if not access_token or jwt_data.get("exp", 0) < time.time() + 60:
                print("Refreshing saved Infinity session...")
                ref = api_request("POST", "/auth/refresh", {"refreshToken": refresh_token})
                access_token = ref["accessToken"]
                refresh_token = ref.get("refreshToken", refresh_token)
            me = api_request("GET", "/auth/me", access_token=access_token)
            username = me.get("username") or username
            user_id = str(me.get("id") or user_id or "")
        except Exception:
            access_token = None

    if not access_token:
        username_input = input("Infinity Username: ").strip()
        password_input = getpass.getpass("Infinity Password: ")
        res = api_request("POST", "/auth/login", {
            "username": username_input,
            "password": password_input,
            "mfaEnabled": True,
            "sessionDurationDays": 30,
        })
        if res.get("mfaRequired") and res.get("mfaToken"):
            mfa_token = res["mfaToken"]
            api_request("POST", "/auth/mfa/send", {"mfaToken": mfa_token})
            code = input("Enter 2FA verification code sent to your email: ").strip()
            res = api_request("POST", "/auth/mfa/verify", {"mfaToken": mfa_token, "code": code, "sessionDurationDays": 30})

        access_token = res["accessToken"]
        refresh_token = res.get("refreshToken", "")
        jwt_data = decode_jwt_payload(access_token)
        user_obj = res.get("user") or {}
        username = user_obj.get("username") or jwt_data.get("username") or username_input
        user_id = str(user_obj.get("id") or jwt_data.get("sub") or "")

    os.makedirs(os.path.dirname(auth_file), exist_ok=True)
    with open(auth_file, "w") as f:
        json.dump({"accessToken": access_token, "refreshToken": refresh_token, "username": username, "userId": user_id}, f, indent=2)
    os.chmod(auth_file, 0o600)

    sess = api_request("POST", "/game/session", {"server": DEFAULT_SERVER_CHANNEL}, access_token=access_token)
    return {
        "username": username,
        "userId": user_id,
        "sessionId": sess["sessionId"],
        "host": sess.get("host") or DEFAULT_HOST,
        "port": int(sess.get("port") or DEFAULT_PORT),
    }

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
    parser = argparse.ArgumentParser(description="SWG Infinity Unified Installer & Launcher")
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
    prefix = runner_cfg.get("wine_prefix") or os.path.expanduser("~/Games/SWG-Infinity")

def check_and_apply_updates(client_dir: str):
    import ssl
    print("Checking for SWG Infinity client updates...")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.swginfinity.com/",
    }

    req = urllib.request.Request(MANIFEST_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20.0) as resp:
            manifest = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Warning: Could not reach manifest server ({e}). Proceeding with local files.")
        return

    files = manifest.get("required", [])
    total_files = len(files)
    downloaded = 0

    for idx, item in enumerate(files, 1):
        rel_path = item["name"].replace("\\", "/")
        expected_md5 = item.get("md5", "").lower()
        expected_size = int(item.get("size", 0))
        url = item["url"]
        full_path = os.path.join(client_dir, rel_path)

        needs_download = True
        if os.path.exists(full_path):
            try:
                if expected_size and os.path.getsize(full_path) == expected_size:
                    if not expected_md5 or compute_md5(full_path) == expected_md5:
                        needs_download = False
            except Exception:
                needs_download = True

        if needs_download:
            size_mb = expected_size / (1024 * 1024)
            print(f"[{idx}/{total_files}] Downloading {rel_path} ({size_mb:.2f} MB)...")
            os.makedirs(os.path.dirname(full_path) or client_dir, exist_ok=True)
            tmp_path = full_path + ".part"

            dl_req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(dl_req, context=ctx, timeout=120.0) as resp, open(tmp_path, "wb") as out:
                shutil.copyfileobj(resp, out, length=262144)

            if expected_md5 and compute_md5(tmp_path) != expected_md5:
                os.remove(tmp_path)
                raise RuntimeError(f"MD5 mismatch on {rel_path}")
            os.replace(tmp_path, full_path)
            downloaded += 1

    with open(os.path.join(client_dir, ".manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print("Client is up to date." if downloaded == 0 else f"Update complete! ({downloaded} files updated)\n")

  #  check_and_apply_updates(client_dir)
  #  session = authenticate_and_create_session(client_dir)
  #  width, height = get_screen_resolution()
  #  ensure_config_files(client_dir, session["host"], session["port"], width, height)

  #  exe_name = next((f for f in os.listdir(client_dir) if f.lower() == "swgemu.exe"), "swgemu.exe")

# Step 4: Construct exact SWG Infinity launch arguments (Standard Windowed Mode)
    game_args = [
        wine_bin,
        exe_name,
        "--",
        "-s", "ClientGame",
        f"loginServerAddress0={session['host']}",
        f"loginServerPort0={session['port']}",
        f"loginClientID={session['username']}",
        "autoConnectToLoginServer=true",
        "-s", "Station",
        f"sessionId={session['sessionId']}",
        "subscriptionFeatures=1",
        "gameFeatures=65535",
        "-s", "SwgClient",
        "allowMultipleInstances=true",
        "-s", "ClientGraphics",
        f"screenWidth={width}",
        f"screenHeight={height}",
        "windowed=true",
        "borderlessWindow=true",
    ]

    env = os.environ.copy()
    env["WINEPREFIX"] = prefix
    env["SWGCLIENT_MEMORY_SIZE_MB"] = "2048"
    if session.get("userId"):
        env["SENTINEL_ACCOUNT_ID"] = str(session["userId"])

    print(f"Launching SWG Infinity ({width}x{height})...")
    subprocess.run(game_args, cwd=client_dir, env=env)

if __name__ == "__main__":
    main()
