# HalDeck – Nutzerdokumentation

## Übersicht

HalDeck verbindet einen **Elgato Stream Deck** mit **LinuxCNC** über das HAL-System (Hardware Abstraction Layer). Die Konfiguration der Tasten erfolgt über eine INI-Datei (`haldeck.ini`).

---

## Grundstruktur der Konfigurationsdatei

Die Datei ist in **Sektionen** aufgeteilt. Jede Sektion beginnt mit einem Namen in eckigen Klammern `[...]`.

```
[General]           ← Allgemeine Einstellungen
[page.1.key.00]     ← Taste 0 auf Seite 1
[page.1.key.01]     ← Taste 1 auf Seite 1
[page.2.key.00]     ← Taste 0 auf Seite 2
[page.11]           ← Splash-Screen Seite 11
```

Kommentare beginnen mit `#`.

---

## 1. Allgemeine Einstellungen `[General]`

```ini
[General]
Verbose    = true    # Ausführliche Konsolenausgabe (true/false)
Brightness = 50      # Helligkeit des Stream Decks (0–100)
```

---

## 2. Seiten und Tastennummern

Das Stream Deck kann bis zu **10 normale Seiten** (Seiten 1–10) und bis zu **10 Splash-Screens** (Seiten 11–20) haben.

Die Tasten eines Stream Decks Original (5×3) sind von links oben nach rechts unten nummeriert:

```
┌─────┬─────┬─────┬─────┬─────┐
│ 00  │ 01  │ 02  │ 03  │ 04  │
├─────┼─────┼─────┼─────┼─────┤
│ 05  │ 06  │ 07  │ 08  │ 09  │
├─────┼─────┼─────┼─────┼─────┤
│ 10  │ 11  │ 12  │ 13  │ 14  │
└─────┴─────┴─────┴─────┴─────┘
```

Der Sektionsname lautet immer: `[page.SEITE.key.NUMMER]`

---

## 3. Tastentypen (`Type`)

Jede Taste bekommt einen Typ zugewiesen. Folgende Typen sind verfügbar:

| Typ             | Beschreibung |
|-----------------|-------------|
| `momentary`     | Standard-Taster mit HAL-Pins (Drücken/Loslassen) |
| `keyboard`      | Simuliert einen Tastendruck auf der PC-Tastatur |
| `display-float` | Zeigt einen HAL-Gleitkommawert (z. B. Achsposition) an |
| `unused`        | Taste ist deaktiviert, kein HAL-Pin wird erstellt |

---

## 4. Typ: `momentary` – Standard-Taster

Erzeugt HAL-Pins für Tastendrücke und LED-Status.

### Erzeugte HAL-Pins

| Pin | Richtung | Bedeutung |
|-----|----------|-----------|
| `haldeck.page.N.ALIAS.out` | Ausgang (BIT) | `true` solange Taste gedrückt |
| `haldeck.page.N.ALIAS.in`  | Eingang (BIT) | Steuert LED/Highlight der Taste |
| `haldeck.page.N.ALIAS.enable` | Eingang (BIT) | (optional) Deaktiviert die Taste wenn `false` |

> **N** = Seitennummer, **ALIAS** = Wert von `PinAlias`

### Alle Parameter

```ini
[page.1.key.00]
Type             = momentary

# HAL-Pin-Name (Standard: zweistellige Tastennummer, z.B. "00")
PinAlias         = Estop

# Bilder für die zwei Zustände der Taste
InactiveImage    = power_red.png    # Bild wenn Taste NICHT gedrückt / Signal LOW
ActiveImage      = power_green.png  # Bild wenn Taste gedrückt / Signal HIGH

# ODER: nur ein Bild für beide Zustände
Image            = power_red.png

# Hintergrundfarben (CSS-Farbnamen oder #RRGGBB)
InactiveBackground = black
ActiveBackground   = white

# Textbeschriftung
InactiveLabel    = START
ActiveLabel      = RUNNING

# Schriftfarben
InactiveLabelColor = white
ActiveLabelColor   = black

# Schriftgröße in Punkten
FontSize         = 20

# Randabstand um das Bild in Pixeln: oben,rechts,unten,links
ImageMargins     = 0,0,0,0

# Text über Bild zeichnen (true/false)
DrawLabelOnImage = false

# Optionalen Enable-Pin erstellen (true/false)
EnablePin        = false
```

### Minimalbeispiel

```ini
[page.1.key.00]
Type          = momentary
PinAlias      = Estop
InactiveImage = power_red.png
ActiveImage   = power_green.png
```

### Beispiel: Nur Text, keine Bilder

```ini
[page.1.key.05]
Type               = momentary
PinAlias           = SpindleStart
InactiveBackground = #003300
ActiveBackground   = #00ff00
InactiveLabelColor = white
ActiveLabelColor   = black
InactiveLabel      = SPINDEL
                     AUS
ActiveLabel        = SPINDEL
                     EIN
FontSize           = 16
```

> **Tipp:** Mehrzeiliger Text wird durch Einrückung der Folgezeilen erreicht.

---

## 5. Typ: `keyboard` – Tastatureingabe simulieren

Diese Taste simuliert einen Tastendruck auf der PC-Tastatur. Es werden **keine HAL-Pins** erstellt.

```ini
[page.2.key.03]
Type            = keyboard
KeyboardKey     = Key.f5          # Sondertaste (pynput-Syntax)
# ODER:
KeyboardKey     = a               # Normales Zeichen

InactiveLabel   = F5
ActiveLabel     = F5
InactiveBackground = black
ActiveBackground   = white
```

### Verfügbare Sondertasten (`Key.*`)

Häufig genutzte Werte für `KeyboardKey`:

| Wert | Taste |
|------|-------|
| `Key.f1` … `Key.f12` | Funktionstasten F1–F12 |
| `Key.space` | Leertaste |
| `Key.enter` | Enter |
| `Key.esc`   | Escape |
| `Key.home`, `Key.end` | Pos1, Ende |
| `Key.page_up`, `Key.page_down` | Bild auf/ab |

---

## 6. Typ: `display-float` – Messwert anzeigen

Zeigt einen Gleitkommawert aus HAL an (z. B. Achsposition). Die Taste reagiert **nicht** auf Tastendruck.

### Erzeugte HAL-Pins

| Pin | Richtung | Bedeutung |
|-----|----------|-----------|
| `haldeck.page.N.ALIAS.value` | Eingang (FLOAT) | Anzuzeigender Wert |

### Alle Parameter

```ini
[page.1.key.03]
Type               = display-float
PinAlias           = PosX

# FloatPin = true aktiviert den .value-HAL-Pin
FloatPin           = true

# Python-Formatstring für die Darstellung
Format             = {:.2f}        # 2 Dezimalstellen (Standard)
# Format           = {:.3f}        # 3 Dezimalstellen
# Format           = {:8.2f}       # 8 Zeichen breit, 2 Dezimalstellen

# Dezimalkomma statt Dezimalpunkt (true = Komma)
DecimalComma       = true

# Minimale Wertänderung für Update (verhindert Flackern)
MinStep            = 0.01

# Minimales Zeitintervall zwischen Updates in Sekunden
MinInterval        = 0.1

# Darstellung
InactiveBackground = black
InactiveLabelColor = white
FontSize           = 18

# Text auf Bild zeichnen (bei display-float sinnvoll wenn Hintergrundbild genutzt wird)
DrawLabelOnImage   = true
```

### Minimalbeispiel

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

## 7. Typ: `unused` – Taste deaktivieren

Deaktiviert eine Taste vollständig. Es werden keine HAL-Pins angelegt und die Taste ist dunkel.

```ini
[page.2.key.04]
Type = unused
```

---

## 8. Splash-Screens (Seiten 11–20)

Splash-Screens zeigen ein Vollbild-Bild über alle Tasten. Sie werden als eigenständige Sektion ohne Tastendefinitionen konfiguriert.

```ini
[page.11]
Type              = splash
SplashImage       = linuxcnc_2.gif    # Bilddatei aus dem assets/-Ordner
SplashBackground  = black             # Hintergrundfarbe für Letterboxing
```

### Empfohlene Bildgrößen

| Stream Deck Modell        | Empfohlene Größe |
|---------------------------|-------------------|
| Original (5×3)            | 360 × 216 px      |
| XL (8×4)                  | 576 × 384 px      |
| Mini (3×2)                | 240 × 240 px      |
| + (4×2)                   | 288 × 216 px      |

> Jede Bildgröße funktioniert – das Bild wird automatisch skaliert.

---

## 9. Seitenumschaltung über HAL

Die aktive Seite kann über HAL-Pins gesteuert werden:

| HAL-Pin                  | Typ  | Richtung | Beschreibung |
|--------------------------|------|----------|--------------|
| `haldeck.page-select`    | S32  | Eingang  | Gewünschte Seite setzen |
| `haldeck.page-current`   | S32  | Ausgang  | Aktuell angezeigte Seite |

### Beispiel in der HAL-Datei

```hal
# Seite 2 aktivieren wenn Taster gedrückt wird:
net page-switch haldeck.page-select <= your-signal-source
```

---

## 10. Bilder und Assets

Bildateien werden im Verzeichnis `assets/` im selben Ordner wie `haldeck.py` abgelegt. Unterstützte Formate: **PNG**, **GIF**, **JPG**.

### Mitgelieferte Bilder

| Dateiname | Beschreibung |
|-----------|-------------|
| `power_red.png` / `power_green.png` | Power-Symbol rot/grün |
| `ref_point_red.png` / `ref_point_green.png` | Referenzpunkt rot/grün |
| `play_green.png`, `play_white.png` | Play |
| `pause_white.png` | Pause |
| `stop_red.png`, `stop_white.png` | Stop |
| `plus_grey.png` / `plus_white.png` | Plus-Symbol |
| `minus_grey.png` / `minus_white.png` | Minus-Symbol |
| `uparrow_white.png` / `downarrow_white.png` | Pfeile auf/ab |
| `leftarrow_white.png` / `rightarrow_white.png` | Pfeile links/rechts |
| `page_up.png` / `page_down.png` | Seite vor/zurück |
| `turtle.png` / `rabbit.png` | Langsam/Schnell (Jog) |
| `stepjog_grey.png` / `stepjog_white.png` | Schrittweiser Jog |
| `home.png` | Home/Referenzfahrt |
| `linuxcnc.gif` / `linuxcnc_2.gif` | LinuxCNC-Logo (Splash) |

---

## 11. Rückwärtskompatibilität (Legacy-Format)

Für Seite 1 kann auch das ältere Format ohne Seitenangabe verwendet werden. Das neue Format hat Vorrang.

```ini
# Altes Format (nur für Seite 1):
[key.00]
Type = momentary
...

# Neues Format (empfohlen):
[page.1.key.00]
Type = momentary
...
```

---

## 12. Vollständiges Beispiel

```ini
[General]
Verbose    = false
Brightness = 70

# ── Seite 1: Hauptsteuerung ──────────────────────────

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

# ── Seite 11: Startbildschirm ────────────────────────

[page.11]
Type             = splash
SplashImage      = linuxcnc_2.gif
SplashBackground = black
```

---

## 13. HAL-Pin-Namensschema

Die automatisch erzeugten HAL-Pins folgen diesem Muster:

```
haldeck.page.<SEITE>.<ALIAS>.<SUFFIX>
```

| Typ | Suffix | Datentyp | Richtung |
|-----|--------|----------|----------|
| momentary | `.out` | BIT | Ausgang |
| momentary | `.in`  | BIT | Eingang |
| momentary | `.enable` | BIT | Eingang |
| display-float | `.value` | FLOAT | Eingang |

**Beispiel** mit `PinAlias = Estop` auf Seite 1:
- `haldeck.page.1.Estop.out` → wird `true` solange Taste gedrückt
- `haldeck.page.1.Estop.in`  → steuert die LED-Anzeige der Taste
