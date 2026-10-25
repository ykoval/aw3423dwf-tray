"""Read-only DDC/CI probe: polls VCP codes on all physical monitors and logs changes.

Never calls SetVCPFeature. Usage:
    python probe_vcp.py snapshot          # print all values once
    python probe_vcp.py watch [log_path]  # poll and log every change
"""
import ctypes
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
dxva2 = ctypes.windll.dxva2


class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [("hPhysicalMonitor", wintypes.HANDLE),
                ("szPhysicalMonitorDescription", wintypes.WCHAR * 128)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

# From the AW3423DWF capability string, minus write-only commands (04, 05, 08).
CODES = [0x02, 0x10, 0x12, 0x14, 0x16, 0x18, 0x1A, 0x52, 0x60, 0x62, 0xAC, 0xAE, 0xB2,
         0xB6, 0xC6, 0xC8, 0xC9, 0xCA, 0xCC, 0xD6, 0xDC, 0xDF, 0xE0, 0xE1, 0xE2, 0xE3,
         0xE5, 0xE8, 0xE9, 0xEC, 0xED, 0xF0, 0xF1, 0xF2, 0xF4, 0xFD]
# Codes that change on their own (timers, frequencies) and would only add noise.
NOISY = {0x02, 0xAC, 0xAE, 0xC6}


def physical_monitors():
    handles = []

    def cb(hmon, hdc, rect, lparam):
        count = wintypes.DWORD()
        if dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)) and count.value:
            arr = (PHYSICAL_MONITOR * count.value)()
            if dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr):
                handles.extend((m.hPhysicalMonitor, m.szPhysicalMonitorDescription) for m in arr)
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    return handles


def read(handle, code, retries=2):
    cur, mx, typ = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
    for _ in range(retries + 1):
        if dxva2.GetVCPFeatureAndVCPFeatureReply(handle, code, ctypes.byref(typ),
                                                 ctypes.byref(cur), ctypes.byref(mx)):
            return cur.value, mx.value
        time.sleep(0.05)
    return None


def snapshot(handle):
    return {code: read(handle, code) for code in CODES}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    mons = physical_monitors()
    if not mons:
        print("No physical monitors with DDC/CI found")
        return 1
    handle, desc = mons[0]
    print(f"Monitor: {desc} ({len(mons)} physical monitor(s))", flush=True)

    if mode == "snapshot":
        for code, val in snapshot(handle).items():
            print(f"0x{code:02X}: {'n/a' if val is None else f'{val[0]} (max {val[1]})'}")
        return 0

    log = open(sys.argv[2], "a", encoding="utf-8") if len(sys.argv) > 2 else None

    def emit(line):
        stamp = time.strftime("%H:%M:%S")
        print(f"{stamp} {line}", flush=True)
        if log:
            log.write(f"{stamp} {line}\n")
            log.flush()

    prev = snapshot(handle)
    emit("baseline " + " ".join(f"{c:02X}={v[0]}" for c, v in prev.items() if v))
    while True:
        cur = snapshot(handle)
        changes = [f"{c:02X}: {prev[c][0] if prev[c] else 'n/a'} -> {v[0]}"
                   for c, v in cur.items() if v and c not in NOISY and (not prev[c] or prev[c][0] != v[0])]
        if changes:
            emit("CHANGE " + "; ".join(changes))
        prev = {c: (cur[c] or prev[c]) for c in CODES}
        time.sleep(0.5)


if __name__ == "__main__":
    sys.exit(main())
