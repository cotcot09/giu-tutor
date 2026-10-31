#!/usr/bin/env python3
"""Run scripts/cms_sync.py every 3 hours in the background, while you're logged in.

    python3 scripts/install_sync.py            # install (safe to re-run)
    python3 scripts/install_sync.py --remove   # uninstall
    python3 scripts/install_sync.py --status   # is it installed? last lines of the log

macOS: a LaunchAgent. Windows: a Task Scheduler task. Linux: a crontab line.
Save your GIU login first: python3 scripts/giu_login.py
"""
import argparse
import os
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNC = os.path.join(ROOT, "scripts", "cms_sync.py")
NAME = "giu-tutor-sync"
LABEL = "com.giututor.sync"  # macOS
TASK = "GIU Tutor sync"      # Windows
MARK = "# giu-tutor-sync"    # Linux crontab
EVERY_HOURS = 3


def log_path():
    if sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Logs")
    else:
        d = os.path.join(os.path.expanduser("~"), ".config", "giu")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, NAME + ".log")


def python_exe():
    if os.name == "nt":  # pythonw.exe runs without a console window popping up
        w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        return w if os.path.exists(w) else sys.executable
    return sys.executable


# ---------- macOS ----------

def plist_path():
    return os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")


def mac_install(log):
    path_env = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{escape(python_exe())}</string>
    <string>{escape(SYNC)}</string>
    <string>--log</string>
    <string>{escape(log)}</string>
  </array>
  <key>WorkingDirectory</key><string>{escape(ROOT)}</string>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>{EVERY_HOURS * 3600}</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>{path_env}</string>
    <key>LANG</key><string>en_US.UTF-8</string>
  </dict>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
"""
    os.makedirs(os.path.dirname(plist_path()), exist_ok=True)
    with open(plist_path(), "w", encoding="utf-8") as f:
        f.write(plist)
    uid = str(os.getuid())
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", plist_path()], check=True)


def mac_remove():
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    if os.path.exists(plist_path()):
        os.remove(plist_path())


def mac_installed():
    return os.path.exists(plist_path())


# ---------- Windows ----------

def win_install(log):
    command = f'"{python_exe()}" "{SYNC}" --log "{log}"'
    subprocess.run(["schtasks", "/Create", "/F", "/SC", "HOURLY", "/MO", str(EVERY_HOURS), "/TN", TASK, "/TR", command],
                   check=True)


def win_remove():
    subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK], capture_output=True)


def win_installed():
    return subprocess.run(["schtasks", "/Query", "/TN", TASK], capture_output=True).returncode == 0


# ---------- Linux ----------

def crontab_lines():
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return r.stdout.splitlines() if r.returncode == 0 else []


def write_crontab(lines):
    subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)


def linux_install(log):
    if not shutil.which("crontab"):
        sys.exit("crontab is not installed; run the sync by hand: python3 scripts/cms_sync.py")
    line = f'0 */{EVERY_HOURS} * * * cd "{ROOT}" && "{python_exe()}" "{SYNC}" --log "{log}" {MARK}'
    write_crontab([l for l in crontab_lines() if MARK not in l] + [line])


def linux_remove():
    if shutil.which("crontab"):
        write_crontab([l for l in crontab_lines() if MARK not in l])


def linux_installed():
    return shutil.which("crontab") is not None and any(MARK in l for l in crontab_lines())


def main():
    ap = argparse.ArgumentParser(description="Run the GIU sync every 3 hours in the background.")
    ap.add_argument("--remove", action="store_true", help="uninstall the background sync")
    ap.add_argument("--status", action="store_true", help="show whether it's installed and the last log lines")
    a = ap.parse_args()
    if sys.platform == "darwin":
        install, remove, installed, how = mac_install, mac_remove, mac_installed, "a LaunchAgent"
    elif os.name == "nt":
        install, remove, installed, how = win_install, win_remove, win_installed, "a Task Scheduler task"
    else:
        install, remove, installed, how = linux_install, linux_remove, linux_installed, "a crontab line"
    log = log_path()
    if a.status:
        print(f"Background sync: {'installed' if installed() else 'not installed'} ({how}). Log: {log}")
        if os.path.exists(log):
            with open(log, encoding="utf-8", errors="replace") as f:
                print("".join(f.readlines()[-15:]), end="")
        return
    if a.remove:
        remove()
        print("Background sync removed.")
        return
    install(log)
    print(f"Background sync installed as {how}: every {EVERY_HOURS} hours while you're logged in.")
    print(f"Log: {log}")
    print("Check it any time: python3 scripts/install_sync.py --status")


if __name__ == "__main__":
    main()
