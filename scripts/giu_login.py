#!/usr/bin/env python3
"""Save your GIU login for scripts/cms_sync.py. Run it in your own terminal, never in a chat:

    python3 scripts/giu_login.py        (Windows: python scripts/giu_login.py)

Username -> ~/.config/giu/username. Password -> your system's secure store:
  macOS    Keychain item "giu-portal" (macOS asks for the password itself)
  Windows  encrypted with your Windows account (DPAPI) in ~/.config/giu/password.dpapi
  Linux    secret-tool (libsecret) if installed, else ~/.config/giu/password readable only by you
Run it again whenever your GIU password changes.
"""
import getpass
import os
import shutil
import subprocess
import sys

CONF = os.path.join(os.path.expanduser("~"), ".config", "giu")
USER_FILE = os.path.join(CONF, "username")
SERVICE = "giu-portal"
DPAPI_FILE = os.path.join(CONF, "password.dpapi")
PLAIN_FILE = os.path.join(CONF, "password")
HINT = "run: python3 scripts/giu_login.py"

PS_SAVE = ("$p = [Console]::In.ReadLine(); "
           "ConvertTo-SecureString $p -AsPlainText -Force | ConvertFrom-SecureString | "
           "Set-Content -Encoding ASCII -Path $env:GIU_DPAPI_FILE")
PS_LOAD = ("$s = (Get-Content -Raw -Path $env:GIU_DPAPI_FILE).Trim() | ConvertTo-SecureString; "
           "[Runtime.InteropServices.Marshal]::PtrToStringBSTR([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))")


def private_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def load_username():
    try:
        with open(USER_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def load_password(user):
    """The saved password, or '' if none is saved."""
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", user, "-w"],
                               capture_output=True, text=True, timeout=60)
            return r.stdout.rstrip("\n") if r.returncode == 0 else ""
        if os.name == "nt":
            if not os.path.exists(DPAPI_FILE):
                return ""
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_LOAD],
                               capture_output=True, text=True, timeout=60, env={**os.environ, "GIU_DPAPI_FILE": DPAPI_FILE})
            return r.stdout.rstrip("\r\n") if r.returncode == 0 else ""
        if shutil.which("secret-tool"):
            r = subprocess.run(["secret-tool", "lookup", "service", SERVICE, "account", user],
                               capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and r.stdout:
                return r.stdout.rstrip("\n")
        with open(PLAIN_FILE, encoding="utf-8") as f:
            return f.read().rstrip("\n")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def save_password(user):
    if sys.platform == "darwin":
        print("Now type your GIU password. macOS asks twice; nothing shows while you type.")
        # -w last with no value: macOS prompts for the password itself, so it never passes through this script.
        # -T /usr/bin/security lets the background sync read it without a pop-up.
        subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", user,
                        "-l", "GIU portal", "-T", "/usr/bin/security", "-w"], check=True)
        return "the macOS Keychain"
    password = getpass.getpass("GIU password (nothing shows while you type): ")
    if not password:
        sys.exit("No password given; nothing saved.")
    if os.name == "nt":
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_SAVE],
                       input=password + "\n", text=True, check=True, env={**os.environ, "GIU_DPAPI_FILE": DPAPI_FILE})
        return "an encrypted file only your Windows account can read"
    if shutil.which("secret-tool"):
        subprocess.run(["secret-tool", "store", "--label=GIU portal", "service", SERVICE, "account", user],
                       input=password, text=True, check=True)
        return "your system keyring"
    private_write(PLAIN_FILE, password + "\n")
    return f"{PLAIN_FILE} (only you can read it; install secret-tool for a keyring)"


def main():
    os.makedirs(CONF, exist_ok=True)
    try:
        os.chmod(CONF, 0o700)
    except OSError:
        pass
    current = load_username()
    user = input(f"GIU username (same as the portal login){f' [{current}]' if current else ''}: ").strip() or current
    user = "".join(user.split())
    if not user:
        sys.exit("No username given; nothing saved.")
    private_write(USER_FILE, user + "\n")
    where = save_password(user)
    print(f"Saved for {user} in {where}.")
    print("Test it: python3 scripts/cms_sync.py --dry-run")


if __name__ == "__main__":
    main()
