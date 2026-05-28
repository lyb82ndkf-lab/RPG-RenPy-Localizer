package com.rpgrtl.engine.xserver.events;

import com.rpgrtl.engine.core.Bitmask;
import com.rpgrtl.engine.xserver.Window;

public class ButtonPress extends InputDeviceEvent {
    public ButtonPress(byte detail, Window root, Window event, Window child, short rootX, short rootY, short eventX, short eventY, Bitmask state) {
        super(4, detail, root, event, child, rootX, rootY, eventX, eventY, state);
    }
}

