#!/usr/bin/env python3
"""Save your GIU login for scripts/cms_sync.py. Type it in your own terminal or a password box, never in a chat:

    python3 scripts/giu_login.py            (Windows: python scripts/giu_login.py)
    python3 scripts/giu_login.py --dialog   a password box instead of the terminal (macOS, Windows)

Username -> ~/.config/giu/username. Password -> your system's secure store:
  macOS    Keychain item "giu-portal" (macOS asks for the password itself)
  Windows  encrypted with your Windows account (DPAPI) in ~/.config/giu/password.dpapi
  Linux    secret-tool (libsecret) if installed, else ~/.config/giu/password readable only by you
Run it again whenever your GIU password changes.
"""
import argparse
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
# Windows password box: the password goes straight from the box into the encrypted file, never through Python.
PS_DIALOG = ("$m = 'Your GIU portal login (same as the CMS)'; "
             "$c = if ($env:GIU_USER) { Get-Credential -UserName $env:GIU_USER -Message $m } else { Get-Credential -Message $m }; "
             "if (-not $c) { exit 1 }; "
             "$c.Password | ConvertFrom-SecureString | Set-Content -Encoding ASCII -Path $env:GIU_DPAPI_FILE; "
             "$c.UserName")


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


def save_password(user, password=None):
    if sys.platform == "darwin":
        # -T /usr/bin/security lets the background sync read it without a pop-up.
        cmd = ["security", "add-generic-password", "-U", "-s", SERVICE, "-a", user, "-l", "GIU portal",
               "-T", "/usr/bin/security", "-w"]
        if password is None:
            print("Now type your GIU password. macOS asks twice; nothing shows while you type.")
            # -w last with no value: macOS prompts for the password itself, so it never passes through this script.
            subprocess.run(cmd, check=True)
        else:
            # From the password box: on the command line for a moment, visible only to your own account.
            subprocess.run(cmd + [password], check=True, capture_output=True)
        return "the macOS Keychain"
    if password is None:
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


def mac_box(prompt, default="", hidden=False):
    """A macOS text box; returns what was typed, or None if cancelled."""
    script = ["on run argv", "activate",
              "display dialog (item 1 of argv) default answer (item 2 of argv)"
              + (" with hidden answer" if hidden else "") + ' with title "GIU Tutor"',
              "return text returned of result", "end run"]
    args = [a for line in script for a in ("-e", line)]
    r = subprocess.run(["osascript", *args, prompt, default], capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def dialog_login(current):
    """--dialog: ask in password boxes, for students who don't use a terminal. Returns (user, where)."""
    if sys.platform == "darwin":
        user = "".join((mac_box("Your GIU username (same as the portal login):", current) or "").split())
        if not user:
            sys.exit("Cancelled; nothing saved.")
        password = mac_box(f"GIU password for {user}:", hidden=True)
        if not password:
            sys.exit("Cancelled; nothing saved.")
        private_write(USER_FILE, user + "\n")
        return user, save_password(user, password)
    if os.name == "nt":
        r = subprocess.run(["powershell", "-NoProfile", "-Command", PS_DIALOG], capture_output=True, text=True,
                           env={**os.environ, "GIU_USER": current, "GIU_DPAPI_FILE": DPAPI_FILE})
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        user = "".join(lines[-1].lstrip("\\").split()) if r.returncode == 0 and lines else ""
        if not user:
            sys.exit("Cancelled; nothing saved.")
        private_write(USER_FILE, user + "\n")
        return user, "an encrypted file only your Windows account can read"
    sys.exit("No password box on Linux; run this in a terminal instead: python3 scripts/giu_login.py")


def main():
    ap = argparse.ArgumentParser(description="Save your GIU login for the sync.")
    ap.add_argument("--dialog", action="store_true", help="ask in a password box instead of the terminal (macOS, Windows)")
    a = ap.parse_args()
    os.makedirs(CONF, exist_ok=True)
    try:
        os.chmod(CONF, 0o700)
    except OSError:
        pass
    current = load_username()
    if a.dialog:
        user, where = dialog_login(current)
    else:
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
