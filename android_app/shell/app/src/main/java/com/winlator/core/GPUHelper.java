package com.winlator.core;

import dalvik.annotation.optimization.CriticalNative;

public final class GPUHelper {
    static {
        System.loadLibrary("winlator");
    }

    private GPUHelper() {}

    public static native String[] vkGetDeviceExtensions();
    @CriticalNative public static native int vkGetApiVersion();
    public static native void setGlobalEGLContext();
}
