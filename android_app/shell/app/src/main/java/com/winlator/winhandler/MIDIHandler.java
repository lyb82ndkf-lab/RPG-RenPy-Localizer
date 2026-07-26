package com.winlator.winhandler;

public final class MIDIHandler {
    static {
        System.loadLibrary("midihandler");
    }

    private MIDIHandler() {}

    public static native long nativeAllocate();
    public static native void destroy(long nativePtr);
    public static native void noteOn(long nativePtr, int channel, int note, int velocity);
    public static native void noteOff(long nativePtr, int channel, int note);
    public static native void keyPressure(long nativePtr, int channel, int key, int value);
    public static native void programChange(long nativePtr, int channel, int program);
    public static native void controlChange(long nativePtr, int channel, int control, int value);
    public static native void pitchBend(long nativePtr, int channel, int value);
    public static native void loadSoundFont(long nativePtr, String soundfontPath);
}
