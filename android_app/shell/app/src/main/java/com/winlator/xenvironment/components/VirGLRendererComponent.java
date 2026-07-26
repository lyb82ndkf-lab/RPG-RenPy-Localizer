package com.winlator.xenvironment.components;

public final class VirGLRendererComponent {
    private final com.rpgrtl.engine.xenvironment.components.VirGLRendererComponent delegate;

    static {
        System.loadLibrary("virglrenderer");
    }

    public VirGLRendererComponent(com.rpgrtl.engine.xenvironment.components.VirGLRendererComponent delegate) {
        this.delegate = delegate;
    }

    @SuppressWarnings("unused")
    private void killConnection(int fd) {
        delegate.killConnectionFromNative(fd);
    }

    @SuppressWarnings("unused")
    private void flushFrontbuffer(int drawableId, int framebuffer) {
        delegate.flushFrontbufferFromNative(drawableId, framebuffer);
    }

    public native long handleNewConnection(int fd);
    public native void handleRequest(long clientPtr);
    public native long getCurrentEGLContextPtr();
    public native void destroyClient(long clientPtr);
    public native void destroyRenderer(long clientPtr);
}
