## Intro

HalDeck provides StreamDeck support for LinuxCNC, allowing deck buttons to reflect and control HAL pins.
This allows creating responsive, tactile user interfaces for LinuxCNC machines.



![HalDeck](images/001.jpg)


## Installation
    
- some packages
```
sudo apt install libhidapi-libusb0 python3-pip python3-pynput usbutils
```

- python3 streamdeck library
```
python3 -m pip install streamdeck  --user --break-system-packages
```    

## Information

HalDeck is built around three key files:

- haldeck.py
    - The main Python script.
    - It handles communication between the StreamDeck device and LinuxCNC/HAL and updates the button states based on HAL pins.

- haldeck.ini
    - The configuration file for button layouts.
    - This file defines pages, button positions, icons, HAL signal assignments, and button behavior.

- haldeck.hal
    - The HAL configuration.  
    - It connects the button definitions from the ini file to real LinuxCNC HAL pins, allowing physical StreamDeck button presses to trigger machine functions.

## Documentation

- Some documentation is available here: ![Documentation](DOcUMENTATION.md)





## Run example / demo

```
git clone https://github.com/talla83/haldeck.git haldeck
cd haldeck
linuxcnc haldeck_demo.ini
```




## Credits

Thanks to all patrons for their support.
www.patreon.com/Talla83
