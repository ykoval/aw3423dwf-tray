"""Windows HDR ("advanced color") state via the DisplayConfig API."""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

QDC_ONLY_ACTIVE_PATHS = 0x2
DEVICE_INFO_GET_TARGET_NAME = 2
DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9
DEVICE_INFO_SET_ADVANCED_COLOR_STATE = 10


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", ctypes.c_uint32), ("Denominator", ctypes.c_uint32)]


class PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32),
                ("modeInfoIdx", ctypes.c_uint32), ("statusFlags", ctypes.c_uint32)]


class PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32), ("modeInfoIdx", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32), ("rotation", ctypes.c_uint32),
                ("scaling", ctypes.c_uint32), ("refreshRate", RATIONAL),
                ("scanLineOrdering", ctypes.c_uint32), ("targetAvailable", wintypes.BOOL),
                ("statusFlags", ctypes.c_uint32)]


class PATH_INFO(ctypes.Structure):
    _fields_ = [("sourceInfo", PATH_SOURCE_INFO), ("targetInfo", PATH_TARGET_INFO),
                ("flags", ctypes.c_uint32)]


class MODE_INFO(ctypes.Structure):
    _fields_ = [("infoType", ctypes.c_uint32), ("id", ctypes.c_uint32),
                ("adapterId", LUID), ("data", ctypes.c_byte * 48)]


class DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("size", ctypes.c_uint32),
                ("adapterId", LUID), ("id", ctypes.c_uint32)]


class TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", DEVICE_INFO_HEADER), ("flags", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32), ("edidManufactureId", ctypes.c_uint16),
                ("edidProductCodeId", ctypes.c_uint16), ("connectorInstance", ctypes.c_uint32),
                ("monitorFriendlyDeviceName", wintypes.WCHAR * 64),
                ("monitorDevicePath", wintypes.WCHAR * 128)]


class ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [("header", DEVICE_INFO_HEADER), ("value", ctypes.c_uint32),
                ("colorEncoding", ctypes.c_uint32), ("bitsPerColorChannel", ctypes.c_uint32)]


class SET_ADVANCED_COLOR_STATE(ctypes.Structure):
    _fields_ = [("header", DEVICE_INFO_HEADER), ("value", ctypes.c_uint32)]


def _active_targets():
    n_paths, n_modes = ctypes.c_uint32(), ctypes.c_uint32()
    if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths),
                                          ctypes.byref(n_modes)):
        return []
    paths = (PATH_INFO * n_paths.value)()
    modes = (MODE_INFO * n_modes.value)()
    if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(n_paths), paths,
                                 ctypes.byref(n_modes), modes, None):
        return []
    return [(p.targetInfo.adapterId, p.targetInfo.id) for p in paths[:n_paths.value]]


def _header(info, kind, adapter, target):
    info.header.type = kind
    info.header.size = ctypes.sizeof(info)
    info.header.adapterId = adapter
    info.header.id = target


def _target_name(adapter, target):
    info = TARGET_DEVICE_NAME()
    _header(info, DEVICE_INFO_GET_TARGET_NAME, adapter, target)
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info)):
        return ""
    return info.monitorFriendlyDeviceName


def _find_target(name_hint):
    targets = _active_targets()
    for adapter, target in targets:
        if name_hint and name_hint.lower() in _target_name(adapter, target).lower():
            return adapter, target
    return targets[0] if targets else None


def get_state(name_hint="AW3423DWF"):
    """Return (supported, enabled) for the monitor, or None if it is not an active display."""
    found = _find_target(name_hint)
    if not found:
        return None
    info = ADVANCED_COLOR_INFO()
    _header(info, DEVICE_INFO_GET_ADVANCED_COLOR_INFO, *found)
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info)):
        return None
    return bool(info.value & 0x1), bool(info.value & 0x2)


def set_enabled(enabled, name_hint="AW3423DWF"):
    found = _find_target(name_hint)
    if not found:
        return False
    info = SET_ADVANCED_COLOR_STATE()
    _header(info, DEVICE_INFO_SET_ADVANCED_COLOR_STATE, *found)
    info.value = 1 if enabled else 0
    return user32.DisplayConfigSetDeviceInfo(ctypes.byref(info.header)) == 0


if __name__ == "__main__":
    for adapter, target in _active_targets():
        print(f"target {target}: {_target_name(adapter, target)!r}")
    print("HDR (supported, enabled):", get_state())
