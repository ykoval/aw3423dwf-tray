# AW3423DWF DDC/CI map (firmware M3B107)

Read with `tools/probe_vcp.py` on 2026-10-24 while switching modes from the monitor OSD.
Values are decimal (hex in brackets).

## Preset mode: VCP 0xE2 (SDR)

| Mode         | E2        | F0        |
|--------------|-----------|-----------|
| Standard     | 0 (0x00)  | 0         |
| Game 1       | 4 (0x04)  | 0         |
| Warm         | 14 (0x0E) | 0         |
| Cool         | 18 (0x12) | 0         |
| Custom Color | 20 (0x14) | 0         |
| Creator DCI-P3 | 27 (0x1B) | 10 (0x0A) |
| Creator sRGB | 11 (0x0B) | 0         |
| Game 2       | 30 (0x1E) | 13 (0x0D) |
| Game 3       | 31 (0x1F) | 14 (0x0E) |
| FPS          | 32 (0x20) | 15 (0x0F) |
| MOBA/RTS     | 33 (0x21) | 16 (0x10) |
| RPG          | 34 (0x22) | 17 (0x11) |
| Sports       | 47 (0x2F) | 19 (0x13) |

Game 1 also sets 0xDC (Display Application) to 5; every other mode leaves it at 0.

Writes that switch each mode (all confirmed by reading E2 back):

- Creator DCI-P3, FPS, MOBA/RTS, RPG, Sports, Game 2, Game 3: 0xF0 = the F0 value above.
- Creator sRGB, Standard, Cool, Warm, Custom Color: 0x14 = 1 / 5 / 8 / 11 / 12.
- Game 1: 0xDC = 5.
- Writing 0xE2 itself is accepted but ignored: it only reports the mode.

Creator's color space (sRGB / DCI-P3) is a separate mode over DDC/CI, and the monitor
keeps a separate brightness for each.

## HDR modes (only while Windows HDR is on; the OSD locks SDR presets)

| Mode             | E2         | F0        |
|------------------|------------|-----------|
| Desktop          | 39 (0x27)  | 52 (0x34) |
| Movie HDR        | 35 (0x23)  | 49 (0x31) |
| Game HDR         | 36 (0x24)  | 50 (0x32) |
| Custom Color HDR | 255 (0xFF) | 10 (0x0A) |
| DisplayHDR       | 58 (0x3A)  | 54 (0x36) |

The "HDR Peak 1000" toggle did not change any polled code.
0xF2 reads 65 while HDR is on and 0 while it is off.

## Dark Stabilizer: Dell's indirect register 0xF4

Taken from DDPM's own log while switching the level in DDPM, then confirmed by writing.

- Set level N (0–3): write 0xF4 = 48 + N.
- Read: write 0xF4 = 63 (selects Dark Stabilizer), then read 0xF4, which returns 48 + N.
  A read of 65535 means the monitor has not answered yet; retry.
- DDPM uses the same register for other gaming settings (it writes 31, 47 and 79 as
  queries), so a reply outside 48–51 is not ours and should be retried.

## Other codes

- 0x10 brightness, 0x12 contrast (0–100). The monitor stores them per mode,
  so they jump when the mode changes.
- 0x14 color preset (color temperature), changes along with the mode.
- 0x60 input source.
