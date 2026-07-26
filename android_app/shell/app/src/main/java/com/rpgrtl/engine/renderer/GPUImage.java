package com.rpgrtl.engine.renderer;

import androidx.annotation.Keep;

import com.rpgrtl.engine.xserver.Drawable;

import java.nio.ByteBuffer;

public class GPUImage extends Texture {
    private long hardwareBufferPtr;
    private long imageKHRPtr;
    private ByteBuffer virtualData;
    private short stride;
    private boolean locked = false;
    private int nativeHandle;
    private final com.winlator.renderer.GPUImage nativePeer = new com.winlator.renderer.GPUImage(this);

    static {
        System.loadLibrary("winlator");
    }

    public GPUImage(Drawable owner) {
        this(owner, true, true);
    }

    public GPUImage(Drawable owner, boolean cpuAccess) {
        this(owner, cpuAccess, true);
    }

    public GPUImage(Drawable owner, boolean cpuAccess, boolean useHALPixelFormatBGRA8888) {
        super(owner);
        hardwareBufferPtr = createHardwareBuffer(owner.width, owner.height, cpuAccess, useHALPixelFormatBGRA8888);
        if (cpuAccess && hardwareBufferPtr != 0) {
            virtualData = lockHardwareBuffer(hardwareBufferPtr);
            locked = true;
        }
    }

    @Override
    public void allocateTexture(short width, short height, ByteBuffer data) {
        if (isAllocated()) return;
        super.allocateTexture(width, height, null);
        imageKHRPtr = createImageKHR(hardwareBufferPtr, textureId);
    }

    @Override
    public void updateFromDrawable() {
        if (!isAllocated() && owner != null) allocateTexture(owner.width, owner.height, null);
        needsUpdate = false;
    }

    public short getStride() {
        return stride;
    }

    @Keep
    public void setStrideFromNative(short stride) {
        this.stride = stride;
    }

    public int getNativeHandle() {
        return nativeHandle;
    }

    @Keep
    public void setNativeHandleFromNative(int nativeHandle) {
        this.nativeHandle = nativeHandle;
    }

    public ByteBuffer getVirtualData() {
        return virtualData;
    }

    @Override
    public void destroy() {
        destroyImageKHR(imageKHRPtr);
        destroyHardwareBuffer(hardwareBufferPtr, locked);
        virtualData = null;
        imageKHRPtr = 0;
        hardwareBufferPtr = 0;
        super.destroy();
    }

    public long getHardwareBufferPtr() {
        return hardwareBufferPtr;
    }

    private long createHardwareBuffer(short width, short height, boolean cpuAccess, boolean useHALPixelFormatBGRA8888) {
        return nativePeer.createHardwareBuffer(width, height, cpuAccess, useHALPixelFormatBGRA8888);
    }

    private void destroyHardwareBuffer(long hardwareBufferPtr, boolean locked) {
        nativePeer.destroyHardwareBuffer(hardwareBufferPtr, locked);
    }

    private ByteBuffer lockHardwareBuffer(long hardwareBufferPtr) {
        return nativePeer.lockHardwareBuffer(hardwareBufferPtr);
    }

    private long createImageKHR(long hardwareBufferPtr, int textureId) {
        return nativePeer.createImageKHR(hardwareBufferPtr, textureId);
    }

    private void destroyImageKHR(long imageKHRPtr) {
        nativePeer.destroyImageKHR(imageKHRPtr);
    }
}
