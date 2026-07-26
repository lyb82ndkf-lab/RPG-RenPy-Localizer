package com.winlator.xconnector;

import dalvik.annotation.optimization.CriticalNative;

public final class XConnectorEpoll {
    private final com.rpgrtl.engine.xconnector.XConnectorEpoll delegate;

    static {
        System.loadLibrary("winlator");
    }

    public XConnectorEpoll(com.rpgrtl.engine.xconnector.XConnectorEpoll delegate) {
        this.delegate = delegate;
    }

    @SuppressWarnings("unused")
    private void handleConnectionShutdown(Object tag) {
        delegate.handleConnectionShutdownFromNative(tag);
    }

    @SuppressWarnings("unused")
    private Object handleNewConnection(long clientPtr, int fd) {
        return delegate.handleNewConnectionFromNative(clientPtr, fd);
    }

    @SuppressWarnings("unused")
    private void handleExistingConnection(Object tag) {
        delegate.handleExistingConnectionFromNative(tag);
    }

    @SuppressWarnings("unused")
    private void killAllConnections() {
        delegate.killAllConnectionsFromNative();
    }

    @CriticalNative public static native void closeFd(int fd);
    public native long nativeAllocate(String sockPath);
    public static native void destroy(long nativePtr);
    public static native void startEpollThread(long nativePtr, boolean multithreadedClients);
    public static native void stopEpollThread(long nativePtr);
    public static native void killConnection(long connectorPtr, long clientPtr);
}
