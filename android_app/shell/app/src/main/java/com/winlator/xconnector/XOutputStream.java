package com.winlator.xconnector;

import java.nio.ByteBuffer;

import dalvik.annotation.optimization.CriticalNative;

public final class XOutputStream {
    static {
        System.loadLibrary("winlator");
    }

    private XOutputStream() {}

    public static native long nativeAllocate(int fd, int initialCapacity);
    @CriticalNative public static native void setAncillaryFd(long nativePtr, int ancillaryFd);
    @CriticalNative public static native void writeByte(long nativePtr, byte value);
    @CriticalNative public static native void writeShort(long nativePtr, short value);
    @CriticalNative public static native void writeInt(long nativePtr, int value);
    @CriticalNative public static native void writeLong(long nativePtr, long value);
    @CriticalNative public static native void writePad(long nativePtr, int length);
    public static native void writeAt(long nativePtr, int position, byte[] data);
    public static native void writeByteBuffer(long nativePtr, ByteBuffer data, int offset, int length);
    public static native boolean sendData(long nativePtr);
    public static native void destroy(long nativePtr);
    @CriticalNative public static native int length(long nativePtr);
}
