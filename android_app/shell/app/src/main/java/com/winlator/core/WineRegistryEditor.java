package com.winlator.core;

public final class WineRegistryEditor {
    static {
        System.loadLibrary("winlator");
    }

    private WineRegistryEditor() {}

    public static native int[] getKeyLocation(String filename, String key);
    public static native int[] getValueLocation(String filename, int[] keyLocation, String name);
}
