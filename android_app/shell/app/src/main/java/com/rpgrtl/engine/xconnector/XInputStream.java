package com.rpgrtl.engine.xconnector;

import com.rpgrtl.engine.xserver.XServer;

import java.nio.ByteBuffer;

import dalvik.annotation.optimization.CriticalNative;

public class XInputStream {
    private final long nativePtr;

    static {
        System.loadLibrary("winlator");
    }

    public XInputStream(int clientFd, int initialCapacity) {
        nativePtr = nativeAllocate(clientFd, initialCapacity);
    }

    public int readMoreData(boolean canReceiveAncillaryMessages) {
        return readMoreData(nativePtr, canReceiveAncillaryMessages);
    }

    public int getAncillaryFd() {
        return getAncillaryFd(nativePtr);
    }

    public int getActivePosition() {
        return getActivePosition(nativePtr);
    }

    public void setActivePosition(int activePosition) {
        setActivePosition(nativePtr, activePosition);
    }

    public int available() {
        return available(nativePtr);
    }

    public byte readByte() {
        return readByte(nativePtr);
    }

    public int readUnsignedByte() {
        return Byte.toUnsignedInt(readByte(nativePtr));
    }

    public short readShort() {
        return readShort(nativePtr);
    }

    public int readUnsignedShort() {
        return Short.toUnsignedInt(readShort(nativePtr));
    }

    public int readInt() {
        return readInt(nativePtr);
    }

    public long readUnsignedInt() {
        return Integer.toUnsignedLong(readInt(nativePtr));
    }

    public long readLong() {
        return readLong(nativePtr);
    }

    public void read(byte[] result) {
        for (int i = 0; i < result.length; i++) result[i] = readByte();
    }

    public ByteBuffer readByteBuffer(int length) {
        return readByteBuffer(nativePtr, length);
    }

    public String readString8(int length) {
        byte[] bytes = new byte[length];
        read(bytes);
        String str = new String(bytes, XServer.LATIN1_CHARSET);
        if ((-length & 3) > 0) skip(-length & 3);
        return str;
    }

    public void skip(int length) {
        skip(nativePtr, length);
    }

    public void destroy() {
        destroy(nativePtr);
    }

    private long nativeAllocate(int fd, int initialCapacity) {
        return com.winlator.xconnector.XInputStream.nativeAllocate(fd, initialCapacity);
    }

    @CriticalNative
    private static byte readByte(long nativePtr) {
        return com.winlator.xconnector.XInputStream.readByte(nativePtr);
    }

    @CriticalNative
    private static short readShort(long nativePtr) {
        return com.winlator.xconnector.XInputStream.readShort(nativePtr);
    }

    @CriticalNative
    private static int readInt(long nativePtr) {
        return com.winlator.xconnector.XInputStream.readInt(nativePtr);
    }

    @CriticalNative
    private static long readLong(long nativePtr) {
        return com.winlator.xconnector.XInputStream.readLong(nativePtr);
    }

    private static ByteBuffer readByteBuffer(long nativePtr, int length) {
        return com.winlator.xconnector.XInputStream.readByteBuffer(nativePtr, length);
    }

    @CriticalNative
    private static void skip(long nativePtr, int length) {
        com.winlator.xconnector.XInputStream.skip(nativePtr, length);
    }

    @CriticalNative
    private static int available(long nativePtr) {
        return com.winlator.xconnector.XInputStream.available(nativePtr);
    }

    private static int readMoreData(long nativePtr, boolean canReceiveAncillaryMessages) {
        return com.winlator.xconnector.XInputStream.readMoreData(nativePtr, canReceiveAncillaryMessages);
    }

    @CriticalNative
    private static int getActivePosition(long nativePtr) {
        return com.winlator.xconnector.XInputStream.getActivePosition(nativePtr);
    }

    @CriticalNative
    private static void setActivePosition(long nativePtr, int activePosition) {
        com.winlator.xconnector.XInputStream.setActivePosition(nativePtr, activePosition);
    }

    @CriticalNative
    private static int getAncillaryFd(long nativePtr) {
        return com.winlator.xconnector.XInputStream.getAncillaryFd(nativePtr);
    }

    private static void destroy(long nativePtr) {
        com.winlator.xconnector.XInputStream.destroy(nativePtr);
    }
}

