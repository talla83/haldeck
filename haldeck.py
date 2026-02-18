#!/usr/bin/env python3
###############################################################
#
# HalDeck – StreamDeck support for LinuxCNC
#
# Enhanced with:
# - Multi-page support (1-20 pages)
# - Per-key image support with caching
# - Full-screen splash screens (pages 11-20)
# - Float value display keys
# - HAL pin-based page switching
# - VM-compatible polling workaround
# - USB keepalive to prevent suspend
#
# Copyright (C) 2026 Peter Damerau
# https://www.talla83.de
#
# This project is based on Deckard by Steve Richardson
# https://github.com/tangentaudio/deckard
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
###############################################################

import os
import hal
import threading
import argparse
import configparser
import time
from enum import Enum
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Transport.Transport import TransportError
from pynput.keyboard import Key as PynKey, Controller

# Global configuration
ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")
HAL = hal.component("haldeck")
keyboard = Controller()

MAX_PAGES = 20  # Pages 1-10: Normal operation, 11-20: Splash screens
verbose = False

def vprint(*args, **kwargs):
    """Print only if verbose mode is enabled"""
    if verbose:
        print(*args, **kwargs)

class KeyTypes(Enum):
    """Supported key types"""
    UNUSED = 0          # Key not configured
    MOMENTARY = 1       # Momentary button (press/release)
    KEYBOARD = 3        # Keyboard key simulation
    DISPLAY_FLOAT = 4   # Display floating point value from HAL

class Key:
    """
    Represents a single key on the StreamDeck
    
    Supports:
    - Momentary buttons with HAL I/O
    - Keyboard key simulation
    - Float value display from HAL
    - Custom images per state
    - Text labels with optional overlay on images
    """
    
    def __init__(self, deckref, halref, confref, id, page):
        """
        Initialize a key
        
        Args:
            deckref: Reference to StreamDeck device
            halref: Reference to HAL component
            confref: Reference to ConfigParser
            id: Key index (0-based)
            page: Page number this key belongs to
        """
        self.deck = deckref
        self.hal = halref
        self.config = confref
        self.configopts = {}
        self.id = id
        self.page = page

        # Load configuration for this key
        # Try page-specific config first: [page.N.key.XX]
        conf_section = "page.{}.key.{:02}".format(self.page, self.id)
        if conf_section not in self.config.sections():
            # Fallback to legacy format for page 1: [key.XX]
            if self.page == 1:
                conf_section = "key.{:02}".format(self.id)
        
        if conf_section in self.config.sections():
            self.configopts = self.config[conf_section]
        else:
            self.config[conf_section] = {}
            self.configopts = self.config[conf_section]

        # Determine key type from config
        match self.configopts.get('Type', 'unused'):
          case "momentary":
            self.type = KeyTypes.MOMENTARY
          case "keyboard":
            self.type = KeyTypes.KEYBOARD
          case "display-float":                     
            self.type = KeyTypes.DISPLAY_FLOAT
          case _:
            self.type = KeyTypes.UNUSED

        # Basic configuration
        self.pin_alias = self.configopts.get('PinAlias', "{:02}".format(id))
            
        self.inactive_label = self.configopts.get('InactiveLabel', '{}.OFF'.format(self.id))
        self.active_label = self.configopts.get('ActiveLabel', '{}.ON'.format(self.id))

        self.inactive_label_color = self.configopts.get('InactiveLabelColor', 'white')
        self.active_label_color = self.configopts.get('ActiveLabelColor', 'black')
        
        self.inactive_background = self.configopts.get('InactiveBackground', 'black')
        self.active_background = self.configopts.get('ActiveBackground', 'white')

        self.keyboard_key = self.configopts.get('KeyboardKey', None)
        
        self.state = False

        # Create HAL pins based on key type
        # Only create pins for configured (non-unused) keys
        if self.type == KeyTypes.MOMENTARY:
            # Momentary button: create output (button press) and input (LED state) pins
            self.hal.newpin(self.pin_name('out'), hal.HAL_BIT, hal.HAL_OUT)
            self.hal.newpin(self.pin_name('in'), hal.HAL_BIT, hal.HAL_IN)

            # Optional enable pin to disable the button
            self.hasEnable = self.configopts.getboolean('EnablePin', False)
            if self.hasEnable:
                self.hal.newpin(self.pin_name('enable'), hal.HAL_BIT, hal.HAL_IN)
         
            self.enabled = True
            
        elif self.type == KeyTypes.KEYBOARD:
            # Keyboard simulation: no HAL pins needed
            self.enabled = True
            self.hasEnable = False
            
        else:
            self.enabled = False
            self.hasEnable = False
 
        # Display-Float specific configuration
        if self.type == KeyTypes.DISPLAY_FLOAT:
            self.float_pin = self.configopts.get('FloatPin')
            self.format_str = self.configopts.get('Format', '{:.2f}')  # Default: 2 decimals
            self.decimal_comma = self.configopts.getboolean('DecimalComma', True)
            self.min_step = self.configopts.getfloat('MinStep', 0.01)  # Minimum change to update
            self.min_interval = self.configopts.getfloat('MinInterval', 0.1)  # Minimum time between updates
            self.display_label_color = self.configopts.get('DisplayLabelColor', self.active_label_color)
            self.display_background = self.configopts.get('DisplayBackground', self.active_background)
            self.enabled = True
            self.hasEnable = False
            self._last_good_value = None
            self._last_update_ts = 0.0
            
            # Create HAL input pin for float value
            if self.float_pin:
                self.hal.newpin(self.pin_name('value'), hal.HAL_FLOAT, hal.HAL_IN)
      
        # Image support
        # InactiveImage: image for released/off state
        # ActiveImage: image for pressed/on state
        # Image: fallback if only one image specified
        self.inactive_image_file = self.configopts.get('InactiveImage', self.configopts.get('Image', None))
        self.active_image_file   = self.configopts.get('ActiveImage',   self.inactive_image_file)

        # Image margins: space around image (top, right, bottom, left)
        margins_str = self.configopts.get('ImageMargins', '0,0,0,0')
        try:
           self.image_margins = [int(v.strip()) for v in margins_str.split(',')]
           if len(self.image_margins) != 4:
               raise ValueError
        except Exception:
           self.image_margins = [0, 0, 0, 0]

        # DrawLabelOnImage: if true, draw text label on top of image
        # if false, image is shown without text overlay
        val = self.configopts.get('DrawLabelOnImage', 'False')
        self.draw_label_on_image = str(val).strip().lower() in ('1', 'true', 'yes', 'on')

        # Image caches for performance
        # Images are loaded once and cached to avoid repeated file I/O
        self._cached_active_image = None
        self._cached_inactive_image = None
            
    def _load_and_scale_image(self, filename):
        """
        Load and scale an image to fit the key size
        
        Args:
            filename: Path to image file (absolute or relative to ASSETS_PATH)
            
        Returns:
            PIL.Image scaled to key size, or None if load fails
        """
        if not filename:
           return None
           
        # Resolve path: absolute or relative to assets directory
        path = filename if os.path.isabs(filename) else os.path.join(ASSETS_PATH, filename)
        
        try:
            # Load image and convert to RGBA for transparency support
            src = Image.open(path).convert("RGBA")
            
            # Scale to key size while maintaining aspect ratio
            # Margins are applied as specified in config
            scaled = PILHelper.create_scaled_key_image(
                self.deck, 
                src, 
                margins=self.image_margins, 
                background="black"
            )
            return scaled
        except Exception as e:
            vprint(f"Failed to load image for key {self.id} on page {self.page}: {e}")
            return None

    def reset(self):
        """
        Reset key state when switching away from this page
        
        Ensures clean state:
        - Releases any pressed keys
        - Resets HAL output pins
        - Clears visual state
        """
        try:
            if self.type == KeyTypes.MOMENTARY:
                # Reset HAL output pin
                self.hal[self.pin_name('out')] = False
                
            elif self.type == KeyTypes.KEYBOARD and self.state:
                # Release any pressed keyboard key
                k = self.keyboard_key
                if k and k.startswith('Key.'):
                    try:
                        _, kenum = k.split('Key.')
                        k = PynKey._member_map_[kenum]
                    except:
                        pass
                if k:
                    keyboard.release(k)
        except Exception as e:
            vprint(f"Reset failed for key {self.id} on page {self.page}: {e}")
        finally:
            # Always reset state and update display
            self.state = False
            self.update_key_image()

    def state_poll(self):
        """
        Poll HAL pins for state changes
        Called periodically from update thread
        
        Handles:
        - Momentary: Check input pin for LED state
        - Display-Float: Check value pin for display updates
        """
        if self.type == KeyTypes.MOMENTARY:
            # Check input pin (for LED state)
            in_state = self.hal[self.pin_name('in')]
            
            # Check enable pin if configured
            if self.hasEnable:
                enable_state = self.hal[self.pin_name('enable')]
            else:
                enable_state = True

            # Update if state or enable changed
            if self.enabled != enable_state or self.state != in_state:
                self.state = in_state
                self.enabled = enable_state
                self.update_key_image()
        
        elif self.type == KeyTypes.DISPLAY_FLOAT:
            import math
            
            try:
                value = self.hal[self.pin_name('value')]
            except Exception:
                value = None
 
            def _is_valid(v):
                """Check if value is valid (not NaN or Inf)"""
                try:
                    return v is not None and not (math.isnan(v) or math.isinf(v))
                except Exception:
                    return False
 
            now = time.time()
            updated = False
 
            # Update if value changed by at least min_step
            if _is_valid(value):
                if self._last_good_value is None or abs(value - self._last_good_value) >= self.min_step:
                    self._last_good_value = float(value)
                    updated = True
 
            # Also update periodically (min_interval) even if value unchanged
            # This ensures display doesn't freeze if value is constant
            if updated or (now - self._last_update_ts) >= self.min_interval:
                self._last_update_ts = now              
                self.state = value
                self.update_key_image()

    def pin_name(self, name):
        """
        Generate full HAL pin name
        
        Format: deckard.page.N.ALIAS.name
        Example: deckard.page.1.Estop.out
        
        Args:
            name: Pin suffix (e.g., 'in', 'out', 'enable', 'value')
            
        Returns:
            Full HAL pin name string
        """
        return 'page.{:1}.{}.{}'.format(self.page, self.pin_alias, name)
    
    def key_change(self, key_state):
        """
        Handle key press/release events
        
        Args:
            key_state: True for press, False for release
        """
        if not self.enabled:
            return

        match self.type:
            case KeyTypes.MOMENTARY:
                # Set HAL output pin
                self.hal[self.pin_name('out')] = key_state
                # Update visual state immediately
                self.state = key_state
                self.update_key_image()
                
            case KeyTypes.KEYBOARD:
                # Simulate keyboard key press/release
                if self.keyboard_key:
                    key = self.keyboard_key
                    
                    # Handle pynput special keys (e.g., 'Key.space')
                    if key.startswith('Key.'):
                        try:
                            [junk, kenum] = key.split('Key.')
                            key = PynKey._member_map_[kenum]
                        except:
                            key = '?'
                        
                    if key_state:
                        keyboard.press(key)
                        self.state = True
                    else:
                        keyboard.release(key)
                        self.state = False

                    self.update_key_image()
 
            case KeyTypes.DISPLAY_FLOAT:
                # Float display keys don't respond to button presses
                return
                   
            case _:
                pass
        
    def render_key_image(self):
        """
        Render the key image based on current state
        
        Rendering priority:
        1. Use configured image if available
        2. Fall back to colored background + text
        3. Apply disabled overlay if key is disabled
        
        Returns:
            Rendered image in native deck format
        """
        with self.deck:
            # Determine label based on state
            label = self.active_label if self.state else self.inactive_label
            
            # For float display, format the value
            if self.type == KeyTypes.DISPLAY_FLOAT:
                try:
                    label = self.format_str.format(self.state)
                except:
                    label = "----"  # Show dashes if formatting fails

            # Determine colors based on state
            color = self.active_label_color if self.state else self.inactive_label_color
            background = 'black' if self.type == KeyTypes.UNUSED else (
               self.active_background if self.state else self.inactive_background
            )

            # Try to use configured image first
            img_file = None
            if self.type != KeyTypes.UNUSED:
                img_file = self.active_image_file if self.state else self.inactive_image_file

            base_image = None
            if img_file:
                # Use cached image if available
                cache_attr = '_cached_active_image' if self.state else '_cached_inactive_image'
                base_image = getattr(self, cache_attr, None)
                
                # Load and cache if not already cached
                if base_image is None:
                    base_image = self._load_and_scale_image(img_file)
                    setattr(self, cache_attr, base_image)

            if base_image is not None:
                # Image available: use it as base
                image = base_image.copy()
                
                # Optionally draw label on top of image
                if self.draw_label_on_image:
                    draw = ImageDraw.Draw(image)
                    fontsize = self.configopts.getint('fontsize', 14)
                    font = ImageFont.truetype(os.path.join(ASSETS_PATH, "Roboto-Regular.ttf"), fontsize)
                    draw.multiline_text(
                        (image.width / 2, image.height / 2),
                        text=label, font=font, anchor="mm", align="center", fill=color
                    )
            else:
                # No image: create colored background with text
                image = PILHelper.create_key_image(self.deck, background=background)
                
                if self.type != KeyTypes.UNUSED:
                    draw = ImageDraw.Draw(image)
                    fontsize = self.configopts.getint('fontsize', 14)
                    font = ImageFont.truetype(os.path.join(ASSETS_PATH, "Roboto-Regular.ttf"), fontsize)
                    draw.multiline_text(
                        (image.width / 2, image.height / 2),
                        text=label, font=font, anchor="mm", align="center", fill=color
                    )

            # Apply disabled overlay if key is not enabled
            if not self.enabled:
                cover_image = Image.new('RGB', image.size, '#000000')
                image = Image.blend(image, cover_image, 0.7)
                image = image.filter(ImageFilter.GaussianBlur(radius=1.25))

            # Convert to native deck format
            return PILHelper.to_native_key_format(self.deck, image)

    def update_key_image(self):
        """
        Update the key image on the physical device
        Renders the image and sends it to the StreamDeck
        """
        image = self.render_key_image()
        with self.deck:
            self.deck.set_key_image(self.id, image)


# Global data structures
keys_by_page = {}           # {page_num: [Key objects]}
splash_pages = {}           # {page_num: {key_index: PIL.Image}}
current_page = 1            # Currently displayed page
deck_ref = None             # Reference to StreamDeck device
hal_page_select_pin = None  # HAL pin name for page selection
hal_page_current_pin = None # HAL pin name for page feedback
press_origin_by_key = {}    # {(deck_id, key_index): page_number} - track where key was pressed


def load_splash_image(deck, image_path, background_color='black', key_spacing=(12, 12)):
    """
    Load a splash image and split it across all keys
    
    The image is scaled to fit the entire deck surface, accounting for the
    physical spacing (bezels) between keys. This creates a seamless full-deck
    image effect.
    
    Args:
        deck: StreamDeck device reference
        image_path: Path to splash image file
        background_color: Background color for letterboxing
        key_spacing: (x_spacing, y_spacing) in pixels between keys
        
    Returns:
        Dict of {key_index: PIL.Image} for each key, or None on error
        
    Technical details:
        The StreamDeck has physical bezels between keys. To create a seamless
        image, we need to account for these gaps. The image is rendered to a
        canvas that includes the gap pixels, then cropped to individual keys.
        This makes the image appear continuous across the deck surface.
    """
    try:
        # Get deck layout information
        rows, cols = deck.key_layout()  # IMPORTANT: returns (rows, cols)
        key_width, key_height = deck.key_image_format()['size']
        spacing_x, spacing_y = key_spacing

        # Calculate dimensions
        # Total key area (without spacing)
        keys_total_w = cols * key_width
        keys_total_h = rows * key_height

        # Additional "hidden" pixels for bezels between keys
        bezel_total_w = spacing_x * (cols - 1)
        bezel_total_h = spacing_y * (rows - 1)

        # Full canvas size including spacing
        full_w = keys_total_w + bezel_total_w
        full_h = keys_total_h + bezel_total_h

        vprint(f"Deck layout: {rows}x{cols}, key={key_width}x{key_height}, spacing={spacing_x}x{spacing_y}")
        vprint(f"Full deck image (incl. spacing): {full_w}x{full_h}")

        # Resolve and load image path
        path = image_path if os.path.isabs(image_path) else os.path.join(ASSETS_PATH, image_path)
        splash = Image.open(path).convert("RGBA")

        # Scale splash image to fit full canvas while maintaining aspect ratio
        # This is the "fit" mode - image fits completely with letterboxing if needed
        img_w, img_h = splash.size
        img_ratio  = img_w / img_h
        deck_ratio = full_w / full_h
        
        if img_ratio > deck_ratio:
            # Image is wider than deck - fit to width
            new_w = full_w
            new_h = int(full_w / img_ratio)
        else:
            # Image is taller than deck - fit to height
            new_h = full_h
            new_w = int(full_h * img_ratio)

        splash = splash.resize((new_w, new_h), Image.LANCZOS)
        
        # Center image on canvas
        offset_x = (full_w - new_w) // 2
        offset_y = (full_h - new_h) // 2

        canvas = Image.new('RGB', (full_w, full_h), background_color)
        canvas.paste(splash, (offset_x, offset_y))

        # Split canvas into individual key tiles
        # Account for bezel spacing in tile positions
        key_images = {}
        for row in range(rows):
            for col in range(cols):
                key_index = row * cols + col

                # Calculate tile position including spacing
                start_x = col * (key_width + spacing_x)
                start_y = row * (key_height + spacing_y)

                left   = start_x
                top    = start_y
                right  = left + key_width
                bottom = top + key_height

                tile = canvas.crop((left, top, right, bottom))
                key_images[key_index] = tile

        vprint(f"Split splash with spacing into {len(key_images)} tiles")
        return key_images

    except Exception as e:
        vprint(f"Error loading splash image: {e}")
        return None

def switch_to_page(new_page, force=False):
    """
    Switch to a different page
    
    Handles both normal pages (with interactive keys) and splash pages
    (full-screen images). When switching pages, all keys on the old page
    are reset to prevent stuck states.
    
    Args:
        new_page: Page number to switch to (1-20)
        force: If True, switch even if already on that page
    """
    global current_page, keys_by_page, splash_pages, deck_ref, hal_page_current_pin, press_origin_by_key
    
    # Validate page number
    if new_page < 1 or new_page > MAX_PAGES:
        vprint("Invalid page number: {}. Must be 1-{}".format(new_page, MAX_PAGES))
        return

    old_page = current_page

    # Reset all keys on old page before switching
    # This prevents stuck keys when switching pages mid-press
    if old_page in keys_by_page:
        for key in keys_by_page[old_page]:
                key.reset()

    # Clear press origin tracking
    # This prevents "lost" release events if user switches page while holding key
    press_origin_by_key.clear()

    # Handle splash pages (full-screen images)
    if new_page in splash_pages:
        vprint("Switching to splash page {}".format(new_page))
        current_page = new_page
        
        # Update HAL feedback pin
        if hal_page_current_pin:
            HAL[hal_page_current_pin] = current_page
            
        # Display splash images on all keys
        if deck_ref:
            splash_images = splash_pages[new_page]
            with deck_ref:
                for key_index, img in splash_images.items():
                    if key_index < deck_ref.key_count():
                        native_img = PILHelper.to_native_key_format(deck_ref, img)
                        deck_ref.set_key_image(key_index, native_img)
        return

    # Handle normal pages with interactive keys
    if new_page not in keys_by_page:
        vprint("Page {} not configured".format(new_page))
        return

    # Skip if already on this page (unless forced)
    if new_page == current_page and not force:
        return

    vprint("Switching from page {} to page {}".format(current_page, new_page))
    current_page = new_page

    # Update HAL feedback pin
    if hal_page_current_pin:
        HAL[hal_page_current_pin] = current_page

    # Update all key images on new page
    if deck_ref:
        with deck_ref:
            for key in keys_by_page[current_page]:
                key.update_key_image()

def page_monitor():
    """
    Monitor HAL pin for page change requests
    
    This thread continuously polls the page-select HAL pin and switches
    pages when a new value is detected. Also implements USB keepalive
    to prevent the device from entering suspend mode.
    
    Runs in background daemon thread.
    """
    global current_page, hal_page_select_pin, deck_ref
    
    last_page_request = current_page
    keepalive_counter = 0
    
    while deck_ref and deck_ref.is_open():
        try:
            # Check for page change request via HAL pin
            if hal_page_select_pin:
                page_request = HAL[hal_page_select_pin]
                
                # Switch if new page requested and different from current
                if page_request != last_page_request and page_request != current_page:
                    switch_to_page(page_request)
                    last_page_request = page_request
            
            # USB Keepalive
            # Query device every 30 seconds to prevent USB suspend
            # This is especially important in VM environments
            keepalive_counter += 1
            if keepalive_counter >= 300:  # 300 * 0.1s = 30 seconds
                try:
                    if deck_ref:
                        with deck_ref:
                            _ = deck_ref.get_brightness()  # Simple query to keep USB active
                        vprint("USB keepalive ping")
                except:
                    pass  # Ignore errors - not critical
                keepalive_counter = 0
            
            # Small sleep to avoid busy loop
            threading.Event().wait(0.1)
            
        except TransportError:
            # Deck was unplugged or connection lost
            break
        except Exception as e:
            vprint("Error in page monitor: {}".format(e))
            break

def key_change_callback(deck, key, state):
    """
    Callback for hardware key press/release events
    
    This is called by the StreamDeck library when a physical key changes state.
    We track which page the key was pressed on to handle page switches during
    key press correctly.
    
    Args:
        deck: StreamDeck device that triggered the event
        key: Key index (0-based)
        state: True for press, False for release
    """
    global current_page, keys_by_page, press_origin_by_key

    vprint("Deck {} Key {} = {} (Page {})".format(deck.id(), key, state, current_page), flush=True)

    deck_key = (deck.id(), key)

    if state:  
        # PRESS: Record which page this key was pressed on
        press_origin_by_key[deck_key] = current_page
        target_page = current_page
    else:      
        # RELEASE: Use the page where key was originally pressed
        # This handles the case where user switches page while holding key
        target_page = press_origin_by_key.pop(deck_key, current_page)

    # Route event to the appropriate key object
    with deck:
        if target_page in keys_by_page and key < len(keys_by_page[target_page]):
            keys_by_page[target_page][key].key_change(state)

def handle_key_event(deck, key_index, state):
    """
    Centralized key event handler
    
    Used by VM polling workaround to route events to correct page.
    Similar to key_change_callback but for polled events.
    
    Args:
        deck: StreamDeck device
        key_index: Key index (0-based)
        state: True for press, False for release
    """
    global current_page, keys_by_page, press_origin_by_key

    deck_key = (deck.id(), key_index)

    if state:
        # PRESS: Record origin page
        press_origin_by_key[deck_key] = current_page
        target_page = current_page
    else:
        # RELEASE: Use origin page
        target_page = press_origin_by_key.pop(deck_key, current_page)

    # Route to key object
    if target_page in keys_by_page and key_index < len(keys_by_page[target_page]):
        keys_by_page[target_page][key_index].key_change(state)


if __name__ == "__main__":
    # Parse command line arguments
    ap = argparse.ArgumentParser(
        prog='deckard.py', 
        description='LinuxCNC StreamDeck support with Multi-Page, Images & Splash Screens'
    )
    ap.add_argument('configfile', help='Path to configuration INI file')
    args = ap.parse_args()

    # Load configuration file
    config = configparser.ConfigParser()
    config.read(args.configfile)

    # Read general configuration section
    section = 'General'
    if section in config.sections():
        configopts = config[section]
    else:
        config[section] = {}
        configopts = config[section]

    verbose = configopts.getboolean('Verbose', False)
    
    # Create HAL pins for page control
    hal_page_select_pin = 'page-select'
    hal_page_current_pin = 'page-current'
    
    HAL.newpin(hal_page_select_pin, hal.HAL_S32, hal.HAL_IN)
    HAL.newpin(hal_page_current_pin, hal.HAL_S32, hal.HAL_OUT)
    
    # Set initial page
    HAL[hal_page_select_pin] = 1
    HAL[hal_page_current_pin] = 1
    
    vprint("Created HAL pins: deckard.{} (IN) and deckard.{} (OUT)".format(
        hal_page_select_pin, hal_page_current_pin))
        
    # Enumerate and open StreamDeck devices
    decks = DeviceManager().enumerate()
    vprint("Deckard found {} deck(s).\n".format(len(decks)))

    for index, deck in enumerate(decks):
        # Skip non-visual devices (e.g., Stream Deck Pedal)
        if not deck.is_visual():
            continue

        # Open and reset device
        deck.open()
        deck.reset()
        deck_ref = deck

        vprint("Opened '{}' device (serial number: '{}', fw: '{}')".format(
            deck.deck_type(), deck.get_serial_number(), deck.get_firmware_version()
        ))

        # Set brightness
        bright = configopts.getint('Brightness', 30)
        vprint("Set brightness to {}".format(bright))
        deck.set_brightness(bright)

        # Parse configuration to find pages
        configured_pages = set()      # Normal pages with interactive keys
        splash_page_configs = {}      # Splash pages with full-screen images
        
        for section in config.sections():
            if section.startswith('page.') and not '.' in section[5:]:
                # Page-level config: [page.N]
                try:
                    page_num = int(section.split('.')[1])
                    if 1 <= page_num <= MAX_PAGES:
                        # Check if it's a splash page
                        if config.has_option(section, 'Type') and config.get(section, 'Type') == 'splash':
                            splash_image = config.get(section, 'SplashImage', fallback=None)
                            splash_bg = config.get(section, 'SplashBackground', fallback='black')
                            if splash_image:
                                splash_page_configs[page_num] = {
                                    'image': splash_image,
                                    'background': splash_bg
                                }
                                vprint(f"Found splash page {page_num}: {splash_image}")
                        else:
                            configured_pages.add(page_num)
                except (ValueError, IndexError):
                    pass
                    
            elif section.startswith('page.'):
                # Key-specific config: [page.N.key.XX]
                try:
                    page_num = int(section.split('.')[1])
                    if 1 <= page_num <= MAX_PAGES:
                        configured_pages.add(page_num)
                except (ValueError, IndexError):
                    pass
                    
            elif section.startswith('key.'):
                # Legacy format: [key.XX] - always page 1
                configured_pages.add(1)
        
        # If no pages configured, assume page 1
        if not configured_pages and not splash_page_configs:
            configured_pages.add(1)
        
        vprint("Found configured pages: {}".format(sorted(configured_pages)))
        vprint("Found splash pages: {}".format(sorted(splash_page_configs.keys())))
        
        # Load splash images
        for page_num, splash_config in splash_page_configs.items():
            # Load and split image across keys
            # key_spacing accounts for physical bezels between keys
            key_images = load_splash_image(
                deck, 
                splash_config['image'], 
                splash_config['background'], 
                key_spacing=(12, 12)  # Typical bezel width for StreamDeck
            )
            if key_images:
                splash_pages[page_num] = key_images
                vprint(f"Loaded splash page {page_num} with {len(key_images)} key images")

        # Initialize keys for normal pages
        for page in sorted(configured_pages):
            keys_by_page[page] = []
            
            # Create Key object for each physical key
            for key in range(deck.key_count()):
                key_obj = Key(deckref=deck, halref=HAL, confref=config, id=key, page=page)
                keys_by_page[page].append(key_obj)
            
            # Count and report configured keys
            configured_keys = sum(1 for k in keys_by_page[page] if k.type != KeyTypes.UNUSED)
            if configured_keys > 0:
                vprint("Page {}: {} configured keys".format(page, configured_keys))
        
        # Start background update thread
        def update():
            """
            Background thread for polling HAL pins and key states
            
            This thread:
            1. Polls HAL input pins for LED state updates
            2. Polls physical key states (VM workaround)
            3. Updates key images when state changes
            """
            prev_key_states = {}  # Track previous states for edge detection
            
            while deck.is_open():
                try:
                    # Skip polling for splash pages (they have no interactive keys)
                    if current_page not in splash_pages and current_page in keys_by_page:
                        # Poll HAL pins for each key on current page
                        for key_obj in keys_by_page[current_page]:
                            key_obj.state_poll()
                        
                        # VM Workaround: Direct key state polling
                        # In VM environments, USB callbacks can be unreliable
                        # This directly polls key states as a fallback
                        try:
                            current_key_states = deck.key_states()
                            for key_id, state in enumerate(current_key_states):
                                prev_state = prev_key_states.get(key_id, False)
                                
                                # Detect state change
                                if state != prev_state:
                                    vprint("VM polling detected: Key {} = {}".format(key_id, state))
                                    
                                    # Route event through centralized handler
                                    if current_page in keys_by_page and key_id < len(keys_by_page[current_page]):
                                        handle_key_event(deck, key_id, state)
                                    
                                    prev_key_states[key_id] = state
                        except:
                            pass  # Fallback if direct polling not supported
                    
                    # Sleep to avoid busy loop
                    time.sleep(0.01)  # 100 Hz polling rate
                                
                except TransportError:
                    # Device disconnected
                    break
        
        # Start background threads
        threading.Thread(target=update, daemon=True).start()
        threading.Thread(target=page_monitor, daemon=True).start()
        
        # Register hardware callback for key events
        deck.set_key_callback(key_change_callback)
        
        # Display initial page
        initial_page = min(keys_by_page.keys()) if keys_by_page else 1
        current_page = initial_page
        HAL[hal_page_current_pin] = initial_page
        switch_to_page(initial_page, force=True)

        # Mark HAL component as ready
        # LinuxCNC will now see this component and its pins
        HAL.ready()

        # Main loop: just keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Clean shutdown on Ctrl+C
            vprint("Shutting down...")
            with deck:
                deck.reset()  # Clear all images
                deck.close()  # Close connection
