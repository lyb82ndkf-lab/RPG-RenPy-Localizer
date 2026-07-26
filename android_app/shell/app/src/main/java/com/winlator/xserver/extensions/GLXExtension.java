package com.winlator.xserver.extensions;

public final class GLXExtension {
    private final com.rpgrtl.engine.xserver.extensions.GLXExtension delegate;

    static {
        System.loadLibrary("gladiorenderer");
    }

    public GLXExtension(com.rpgrtl.engine.xserver.extensions.GLXExtension delegate) {
        this.delegate = delegate;
    }

    @SuppressWarnings("unused")
    private short[] getWindowSize(int windowId) {
        return delegate.getWindowSizeFromNative(windowId);
    }

    @SuppressWarnings("unused")
    private void clearWindowContent(int windowId) {
        delegate.clearWindowContentFromNative(windowId);
    }

    @SuppressWarnings("unused")
    private boolean updateWindowContent(int drawableId, short width, short height, boolean flipY) {
        return delegate.updateWindowContentFromNative(drawableId, width, height, flipY);
    }

    @SuppressWarnings("unused")
    private long getGLXContextPtr(int clientFd, int id) {
        return delegate.getGLXContextPtrFromNative(clientFd, id);
    }

    public native long createGLContext(int clientFd);
    public native void destroyGLContext(long contextPtr);
    public native long createGLXContext(int contextId, long sharedContextPtr);
    public native void destroyGLXContext(long contextPtr);
}
