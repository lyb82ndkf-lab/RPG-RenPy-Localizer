package com.winlator.sysvshm;

import java.nio.ByteBuffer;

public final class SysVSharedMemory {
    static {
        System.loadLibrary("winlator");
    }

    private SysVSharedMemory() {}

    public static native int createMemoryFd(String name, int size);
    public static native int ashmemCreateRegion(int index, long size);
    public static native ByteBuffer mapSHMSegment(int fd, long size, int offset, boolean readonly);
    public static native void unmapSHMSegment(ByteBuffer data, long size);
}
