package com.winlator.renderer;

import java.nio.ByteBuffer;

public final class GPUImage {
    private final com.rpgrtl.engine.renderer.GPUImage delegate;

    static {
        System.loadLibrary("winlator");
    }

    public GPUImage(com.rpgrtl.engine.renderer.GPUImage delegate) {
        this.delegate = delegate;
    }

    @SuppressWarnings("unused")
    private void setStride(short stride) {
        delegate.setStrideFromNative(stride);
    }

    @SuppressWarnings("unused")
    private void setNativeHandle(int nativeHandle) {
        delegate.setNativeHandleFromNative(nativeHandle);
    }

    public native long createHardwareBuffer(short width, short height, boolean cpuAccess, boolean useHALPixelFormatBGRA8888);
    public native void destroyHardwareBuffer(long hardwareBufferPtr, boolean locked);
    public native ByteBuffer lockHardwareBuffer(long hardwareBufferPtr);
    public native long createImageKHR(long hardwareBufferPtr, int textureId);
    public native void destroyImageKHR(long imageKHRPtr);
}
