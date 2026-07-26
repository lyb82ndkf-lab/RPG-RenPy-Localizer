package com.rpgrtl.engine.xconnector;

import com.rpgrtl.engine.xserver.XServer;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.util.concurrent.locks.ReentrantLock;

import dalvik.annotation.optimization.CriticalNative;

public class XOutputStream {
    private final ReentrantLock lock = new ReentrantLock();
    private final long nativePtr;

    static {
        System.loadLibrary("winlator");
    }

    public XOutputStream(int clientFd, int initialCapacity) {
        nativePtr = nativeAllocate(clientFd, initialCapacity);
    }

    public void setAncillaryFd(int ancillaryFd) {
        setAncillaryFd(nativePtr, ancillaryFd);
    }

    public void writeByte(byte value) {
        writeByte(nativePtr, value);
    }

    public void writeShort(short value) {
        writeShort(nativePtr, value);
    }

    public void writeInt(int value) {
        writeInt(nativePtr, value);
    }

    public void writeLong(long value) {
        writeLong(nativePtr, value);
    }

    public void writeString8(String str) {
        byte[] bytes = str.getBytes(XServer.LATIN1_CHARSET);
        int length = -str.length() & 3;
        write(bytes);
        if (length > 0) writePad(length);
    }

    public void write(byte[] data) {
        write(data, 0, data.length);
    }

    public void write(byte[] data, int offset, int length) {
        for (int i = offset; i < length; i++) writeByte(nativePtr, data[i]);
    }

    public void writeAt(int position, byte[] data) {
        writeAt(nativePtr, position, data);
    }

    public void write(ByteBuffer data) {
        if (data.isDirect()) {
            writeByteBuffer(nativePtr, data, data.position(), data.remaining());
        }
        else {
            for (int i = data.position(), length = data.remaining(); i < length; i++) {
                writeByte(nativePtr, data.get(i));
            }
        }
    }

    public void writePad(int length) {
        writePad(nativePtr, length);
    }

    public XStreamLock lock() {
        return new OutputStreamLock();
    }

    public void destroy() {
        destroy(nativePtr);
    }

    private class OutputStreamLock implements XStreamLock {
        public OutputStreamLock() {
            lock.lock();
        }

        @Override
        public void close() throws IOException {
            try {
                if (!sendData(nativePtr)) throw new IOException("Failed to send data.");
            }
            finally {
                lock.unlock();
            }
        }
    }

    public int length() {
        return length(nativePtr);
    }

    private long nativeAllocate(int fd, int initialCapacity) {
        return com.winlator.xconnector.XOutputStream.nativeAllocate(fd, initialCapacity);
    }

    @CriticalNative
    private static void setAncillaryFd(long nativePtr, int ancillaryFd) {
        com.winlator.xconnector.XOutputStream.setAncillaryFd(nativePtr, ancillaryFd);
    }

    @CriticalNative
    private static void writeByte(long nativePtr, byte value) {
        com.winlator.xconnector.XOutputStream.writeByte(nativePtr, value);
    }

    @CriticalNative
    private static void writeShort(long nativePtr, short value) {
        com.winlator.xconnector.XOutputStream.writeShort(nativePtr, value);
    }

    @CriticalNative
    private static void writeInt(long nativePtr, int value) {
        com.winlator.xconnector.XOutputStream.writeInt(nativePtr, value);
    }

    @CriticalNative
    private static void writeLong(long nativePtr, long value) {
        com.winlator.xconnector.XOutputStream.writeLong(nativePtr, value);
    }

    @CriticalNative
    private static void writePad(long nativePtr, int length) {
        com.winlator.xconnector.XOutputStream.writePad(nativePtr, length);
    }

    private static void writeAt(long nativePtr, int position, byte[] data) {
        com.winlator.xconnector.XOutputStream.writeAt(nativePtr, position, data);
    }

    private static void writeByteBuffer(long nativePtr, ByteBuffer data, int offset, int length) {
        com.winlator.xconnector.XOutputStream.writeByteBuffer(nativePtr, data, offset, length);
    }

    private static boolean sendData(long nativePtr) {
        return com.winlator.xconnector.XOutputStream.sendData(nativePtr);
    }

    private static void destroy(long nativePtr) {
        com.winlator.xconnector.XOutputStream.destroy(nativePtr);
    }

    @CriticalNative
    private static int length(long nativePtr) {
        return com.winlator.xconnector.XOutputStream.length(nativePtr);
    }
}

