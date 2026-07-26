package com.winlator.xenvironment.components;

public final class VortekRendererComponent {
    private final com.rpgrtl.engine.xenvironment.components.VortekRendererComponent delegate;

    static {
        System.loadLibrary("vortekrenderer");
    }

    public VortekRendererComponent(com.rpgrtl.engine.xenvironment.components.VortekRendererComponent delegate) {
        this.delegate = delegate;
    }

    @SuppressWarnings("unused")
    private int getWindowWidth(int windowId) {
        return delegate.getWindowWidthFromNative(windowId);
    }

    @SuppressWarnings("unused")
    private int getWindowHeight(int windowId) {
        return delegate.getWindowHeightFromNative(windowId);
    }

    @SuppressWarnings("unused")
    private long getWindowHardwareBuffer(int windowId, boolean useHALPixelFormatBGRA8888) {
        return delegate.getWindowHardwareBufferFromNative(windowId, useHALPixelFormatBGRA8888);
    }

    @SuppressWarnings("unused")
    private void updateWindowContent(int windowId) {
        delegate.updateWindowContentFromNative(windowId);
    }

    public native long createVkContext(int clientFd, Object options);
    public native void destroyVkContext(long contextPtr);
    public native void initVulkanWrapper(String nativeLibraryDir, String libvulkanPath);
    public native boolean handleExtraDataRequest(long contextPtr, int requestCode, int requestLength);
}
