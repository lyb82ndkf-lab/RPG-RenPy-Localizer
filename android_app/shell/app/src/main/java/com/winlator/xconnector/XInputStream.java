package com.winlator.xconnector;

import java.nio.ByteBuffer;

import dalvik.annotation.optimization.CriticalNative;

public final class XInputStream {
    static {
        System.loadLibrary("winlator");
    }

    private XInputStream() {}

    public static native long nativeAllocate(int fd, int initialCapacity);
    @CriticalNative public static native byte readByte(long nativePtr);
    @CriticalNative public static native short readShort(long nativePtr);
    @CriticalNative public static native int readInt(long nativePtr);
    @CriticalNative public static native long readLong(long nativePtr);
    public static native ByteBuffer readByteBuffer(long nativePtr, int length);
    @CriticalNative public static native void skip(long nativePtr, int length);
    @CriticalNative public static native int available(long nativePtr);
    public static native int readMoreData(long nativePtr, boolean canReceiveAncillaryMessages);
    @CriticalNative public static native int getActivePosition(long nativePtr);
    @CriticalNative public static native void setActivePosition(long nativePtr, int activePosition);
    @CriticalNative public static native int getAncillaryFd(long nativePtr);
    public static native void destroy(long nativePtr);
}
