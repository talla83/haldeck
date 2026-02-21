# HalDeck – User Documentation

## Overview

HalDeck connects an **Elgato Stream Deck** to **LinuxCNC** via the HAL system (Hardware Abstraction Layer). Keys are configured through an INI file (`haldeck.ini`).

---

## Basic Structure of the Configuration File

The file is divided into **sections**. Each section starts with a name in square brackets `[...]`.

```
[General]           ← General settings
[page.1.key.00]     ← Key 0 on page 1
[page.1.key.01]     ← Key 1 on page 1
[page.2.key.00]     ← Key 0 on page 2
[page.11]           ← Splash screen page 11
```

Comments start with `#`.

---

## 1. General Settings `[General]`

```ini
[General]
Verbose    = true    # Verbose console output (true/false)
Brightness = 50      # Stream Deck brightness (0–100)
```

---

## 2. Pages and Key Numbers

The Stream Deck supports up to **10 normal pages** (pages 1–10) and up to **10 splash screens** (pages 11–20).

Keys on a Stream Deck Original (5×3) are numbered from top-left to bottom-right:

```
┌─────┬─────┬─────┬─────┬─────┐
│ 00  │ 01  │ 02  │ 03  │ 04  │
├─────┼─────┼─────┼─────┼─────┤
│ 05  │ 06  │ 07  │ 08  │ 09  │
├─────┼─────┼─────┼─────┼─────┤
│ 10  │ 11  │ 12  │ 13  │ 14  │
└─────┴─────┴─────┴─────┴─────┘
```

The section name always follows the pattern: `[page.PAGE.key.NUMBER]`

---

## 3. Key Types (`Type`)

Every key must be assigned a type. The following types are available:

| Type            | Description |
|-----------------|-------------|
| `momentary`     | Standard push button with HAL pins (press/release) |
| `keyboard`      | Simulates a keyboard key press on the PC |
| `display-float` | Displays a HAL floating-point value (e.g. axis position) |
| `unused`        | Key is disabled, no HAL pin is created |

---

## 4. Type: `momentary` – Push Button

Creates HAL pins for key presses and LED status.

### Created HAL Pins

| Pin | Direction | Description |
|-----|-----------|-------------|
| `haldeck.page.N.ALIAS.out` | Output (BIT) | `true` while key is pressed |
| `haldeck.page.N.ALIAS.in`  | Input (BIT)  | Controls LED/highlight of the key |
| `haldeck.page.N.ALIAS.enable` | Input (BIT) | (optional) Disables the key when `false` |

> **N** = page number, **ALIAS** = value of `PinAlias`

### All Parameters

```ini
[page.1.key.00]
Type             = momentary

# HAL pin name (default: two-digit key number, e.g. "00")
PinAlias         = Estop

# Images for the two key states
InactiveImage    = power_red.png    # Image when key is NOT pressed / signal LOW
ActiveImage      = power_green.png  # Image when key is pressed / signal HIGH

# OR: single image for both states
Image            = power_red.png

# Background colors (CSS color names or #RRGGBB)
InactiveBackground = black
ActiveBackground   = white

# Text labels
InactiveLabel    = START
ActiveLabel      = RUNNING

# Font colors
InactiveLabelColor = white
ActiveLabelColor   = black

# Font size in points
FontSize         = 20

# Image padding in pixels: top,right,bottom,left
ImageMargins     = 0,0,0,0

# Draw text label on top of image (true/false)
DrawLabelOnImage = false

# Create optional enable pin (true/false)
EnablePin        = false
```

### Minimal Example

```ini
[page.1.key.00]
Type          = momentary
PinAlias      = Estop
InactiveImage = power_red.png
ActiveImage   = power_green.png
```

### Example: Text Only, No Images

```ini
[page.1.key.05]
Type               = momentary
PinAlias           = SpindleStart
InactiveBackground = #003300
ActiveBackground   = #00ff00
InactiveLabelColor = white
ActiveLabelColor   = black
InactiveLabel      = SPINDLE
                     OFF
ActiveLabel        = SPINDLE
                     ON
FontSize           = 16
```

> **Tip:** Multi-line text is achieved by indenting the continuation lines.

---

## 5. Type: `keyboard` – Keyboard Input Simulation

This key simulates a keyboard key press on the PC. **No HAL pins** are created.

```ini
[page.2.key.03]
Type            = keyboard
KeyboardKey     = Key.f5          # Special key (pynput syntax)
# OR:
KeyboardKey     = a               # Regular character

InactiveLabel   = F5
ActiveLabel     = F5
InactiveBackground = black
ActiveBackground   = white
```

### Available Special Keys (`Key.*`)

Commonly used values for `KeyboardKey`:

| Value | Key |
|-------|-----|
| `Key.f1` … `Key.f12` | Function keys F1–F12 |
| `Key.space` | Space bar |
| `Key.enter` | Enter |
| `Key.esc`   | Escape |
| `Key.home`, `Key.end` | Home, End |
| `Key.page_up`, `Key.page_down` | Page Up, Page Down |

---

## 6. Type: `display-float` – Display a Measured Value

Displays a floating-point value from HAL (e.g. axis position). The key does **not** respond to button presses.

### Created HAL Pins

| Pin | Direction | Description |
|-----|-----------|-------------|
| `haldeck.page.N.ALIAS.value` | Input (FLOAT) | Value to display |

### All Parameters

```ini
[page.1.key.03]
Type               = display-float
PinAlias           = PosX

# FloatPin = true enables the .value HAL pin
FloatPin           = true

# Python format string for display
Format             = {:.2f}        # 2 decimal places (default)
# Format           = {:.3f}        # 3 decimal places
# Format           = {:8.2f}       # 8 characters wide, 2 decimal places

# Use decimal comma instead of decimal point (true = comma)
DecimalComma       = true

# Minimum value change to trigger an update (prevents flickering)
MinStep            = 0.01

# Minimum time interval between updates in seconds
MinInterval        = 0.1

# Display styling
InactiveBackground = black
InactiveLabelColor = white
FontSize           = 18

# Draw label on top of image (useful for display-float with a background image)
DrawLabelOnImage   = true
```

### Minimal Example

```ini
[page.1.key.03]
Type               = display-float
PinAlias           = PosX
FloatPin           = true
Format             = {:.2f}
FontSize           = 18
InactiveBackground = black
InactiveLabelColor = white
```

---

## 7. Type: `unused` – Disable a Key

Completely disables a key. No HAL pins are created and the key remains dark.

```ini
[page.2.key.04]
Type = unused
```

---

## 8. Splash Screens (Pages 11–20)

Splash screens display a full-screen image across all keys. They are configured as a standalone section without individual key definitions.

```ini
[page.11]
Type              = splash
SplashImage       = linuxcnc_2.gif    # Image file from the assets/ folder
SplashBackground  = black             # Background color for letterboxing
```

### Recommended Image Sizes

| Stream Deck Model         | Recommended Size |
|---------------------------|------------------|
| Original (5×3)            | 360 × 216 px     |
| XL (8×4)                  | 576 × 384 px     |
| Mini (3×2)                | 240 × 240 px     |
| + (4×2)                   | 288 × 216 px     |

> Any image size works – the image is scaled automatically.

---

## 9. Page Switching via HAL

The active page can be controlled via HAL pins:

| HAL Pin                  | Type | Direction | Description |
|--------------------------|------|-----------|-------------|
| `haldeck.page-select`    | S32  | Input     | Set the desired page |
| `haldeck.page-current`   | S32  | Output    | Currently displayed page |

### Example in the HAL File

```hal
# Switch to page 2 when a signal goes high:
net page-switch haldeck.page-select <= your-signal-source
```

---

## 10. Images and Assets

Image files are stored in the `assets/` directory in the same folder as `haldeck.py`. Supported formats: **PNG**, **GIF**, **JPG**.

### Included Images

| Filename | Description |
|----------|-------------|
| `power_red.png` / `power_green.png` | Power symbol red/green |
| `ref_point_red.png` / `ref_point_green.png` | Reference point red/green |
| `play_green.png`, `play_white.png` | Play |
| `pause_white.png` | Pause |
| `stop_red.png`, `stop_white.png` | Stop |
| `plus_grey.png` / `plus_white.png` | Plus symbol |
| `minus_grey.png` / `minus_white.png` | Minus symbol |
| `uparrow_white.png` / `downarrow_white.png` | Arrows up/down |
| `leftarrow_white.png` / `rightarrow_white.png` | Arrows left/right |
| `page_up.png` / `page_down.png` | Page forward/back |
| `turtle.png` / `rabbit.png` | Slow/Fast (Jog) |
| `stepjog_grey.png` / `stepjog_white.png` | Step jog |
| `home.png` | Home/reference run |
| `linuxcnc.gif` / `linuxcnc_2.gif` | LinuxCNC logo (Splash) |

---

## 11. Backward Compatibility (Legacy Format)

For page 1, the older format without a page number is also supported. The new format takes precedence.

```ini
# Old format (page 1 only):
[key.00]
Type = momentary
...

# New format (recommended):
[page.1.key.00]
Type = momentary
...
```

---

## 12. Complete Example

```ini
[General]
Verbose    = false
Brightness = 70

# ── Page 1: Main Control ──────────────────────────────

[page.1.key.00]
Type           = momentary
PinAlias       = Estop
InactiveImage  = power_red.png
ActiveImage    = power_green.png

[page.1.key.01]
Type           = momentary
PinAlias       = MachineOn
InactiveBackground = #220000
ActiveBackground   = #00cc00
InactiveLabelColor = white
ActiveLabelColor   = black
InactiveLabel  = MACHINE
                 OFF
ActiveLabel    = MACHINE
                 ON
FontSize       = 16

[page.1.key.03]
Type               = display-float
PinAlias           = PosX
FloatPin           = true
Format             = {:.3f}
FontSize           = 18
InactiveBackground = black
InactiveLabelColor = white

[page.1.key.09]
Type           = keyboard
KeyboardKey    = Key.f5
InactiveLabel  = MDI
ActiveLabel    = MDI
InactiveBackground = #001a33
ActiveBackground   = #0055ff
FontSize       = 18

[page.1.key.14]
Type = unused

# ── Page 11: Startup Screen ───────────────────────────

[page.11]
Type             = splash
SplashImage      = linuxcnc_2.gif
SplashBackground = black
```

---

## 13. HAL Pin Naming Scheme

All automatically created HAL pins follow this pattern:

```
haldeck.page.<PAGE>.<ALIAS>.<SUFFIX>
```

| Type | Suffix | Data Type | Direction |
|------|--------|-----------|-----------|
| momentary | `.out` | BIT | Output |
| momentary | `.in`  | BIT | Input |
| momentary | `.enable` | BIT | Input |
| display-float | `.value` | FLOAT | Input |

**Example** with `PinAlias = Estop` on page 1:
- `haldeck.page.1.Estop.out` → `true` while the key is pressed
- `haldeck.page.1.Estop.in`  → controls the LED highlight of the key
