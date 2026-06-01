package com.rpgrtl.engine.xserver.events;

import com.rpgrtl.engine.core.Bitmask;
import com.rpgrtl.engine.xserver.Window;

public class KeyPress extends InputDeviceEvent {
    public KeyPress(byte keycode, Window root, Window event, Window child, short rootX, short rootY, short eventX, short eventY, Bitmask state) {
        super(2, keycode, root, event, child, rootX, rootY, eventX, eventY, state);
    }
}

