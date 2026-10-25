"""AW3423DWF preset modes (see VCP_MAP.md).

Each mode is switched by writing `value` to VCP `code`; the monitor then reports
`e2` in VCP 0xE2, which is how a switch is verified.
"""
from dataclasses import dataclass

MODEL = "AW3423DWF"

VCP_BRIGHTNESS = 0x10
VCP_CONTRAST = 0x12
VCP_MODE = 0xE2
VCP_HDR_ACTIVE = 0xF2  # 65 while the monitor is in HDR, 0 otherwise

# Dell's indirect register: writing 48 + level sets Dark Stabilizer; writing 63 selects
# it for reading, after which 0xF4 reads back 48 + level (65535 while the monitor is busy).
VCP_DELL_COMMAND = 0xF4
DARK_STABILIZER_BASE = 48
DARK_STABILIZER_QUERY = 63
DARK_STABILIZER_LEVELS = range(4)


@dataclass(frozen=True)
class Mode:
    name: str
    code: int
    value: int
    e2: int
    hdr: bool = False


SDR_MODES = [
    # Creator with the DCI-P3 color space; Creator sRGB is left to the monitor menu.
    Mode("Creator", 0xF0, 10, 27),
    Mode("Standard", 0x14, 5, 0),
    Mode("Warm", 0x14, 11, 14),
    Mode("Cool", 0x14, 8, 18),
    Mode("Custom Color", 0x14, 12, 20),
    Mode("FPS", 0xF0, 15, 32),
    Mode("MOBA/RTS", 0xF0, 16, 33),
    Mode("RPG", 0xF0, 17, 34),
    Mode("Sports", 0xF0, 19, 47),
    Mode("Game 1", 0xDC, 5, 4),
    Mode("Game 2", 0xF0, 13, 30),
    Mode("Game 3", 0xF0, 14, 31),
]

HDR_MODES = [
    Mode("Desktop", 0xF0, 52, 39, hdr=True),
    Mode("Movie HDR", 0xF0, 49, 35, hdr=True),
    Mode("Game HDR", 0xF0, 50, 36, hdr=True),
    Mode("DisplayHDR", 0xF0, 54, 58, hdr=True),
]

# Not offered in the app (Creator sRGB works via 0x14 = 1, Custom Color HDR has no
# working write); listed so the current mode is still named when set from the OSD.
_DISPLAY_ONLY = {11: "Creator sRGB", 255: "Custom Color HDR"}

_BY_E2 = {m.e2: m.name for m in SDR_MODES + HDR_MODES}


def name_for(e2):
    if e2 is None:
        return None
    return _BY_E2.get(e2) or _DISPLAY_ONLY.get(e2) or f"unknown ({e2})"
