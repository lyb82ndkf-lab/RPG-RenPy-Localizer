package com.rpgrtl.engine.xenvironment.components;

import android.opengl.GLES20;

import androidx.annotation.Keep;

import com.rpgrtl.engine.renderer.Texture;
import com.rpgrtl.engine.xconnector.ConnectedClient;
import com.rpgrtl.engine.xconnector.ConnectionHandler;
import com.rpgrtl.engine.xconnector.RequestHandler;
import com.rpgrtl.engine.xconnector.UnixSocketConfig;
import com.rpgrtl.engine.xconnector.XConnectorEpoll;
import com.rpgrtl.engine.xenvironment.EnvironmentComponent;
import com.rpgrtl.engine.xserver.Drawable;
import com.rpgrtl.engine.xserver.XServer;

import java.io.IOException;

public class VirGLRendererComponent extends EnvironmentComponent implements ConnectionHandler, RequestHandler {
    private final XServer xServer;
    private final UnixSocketConfig socketConfig;
    private final com.winlator.xenvironment.components.VirGLRendererComponent nativePeer;
    private XConnectorEpoll connector;

    static {
        System.loadLibrary("virglrenderer");
    }

    public VirGLRendererComponent(XServer xServer, UnixSocketConfig socketConfig) {
        this.xServer = xServer;
        this.socketConfig = socketConfig;
        this.nativePeer = new com.winlator.xenvironment.components.VirGLRendererComponent(this);
    }

    @Override
    public void start() {
        if (connector != null) return;
        connector = new XConnectorEpoll(socketConfig, this, this);
        connector.setInitialInputBufferCapacity(0);
        connector.setInitialOutputBufferCapacity(0);
        connector.start();
    }

    @Override
    public void stop() {
        if (connector != null) {
            connector.destroy();
            connector = null;
        }
    }

    @Keep
    public void killConnectionFromNative(int fd) {
        connector.killConnection(connector.getClientWidthFd(fd));
    }

    @Override
    public void handleConnectionShutdown(ConnectedClient client) {
        long clientPtr = (long)client.getTag();
        destroyClient(clientPtr);
    }

    @Override
    public void handleNewConnection(ConnectedClient client) {
        long clientPtr = handleNewConnection(client.fd);
        client.setTag(clientPtr);
    }

    @Override
    public boolean handleRequest(ConnectedClient client) throws IOException {
        long clientPtr = (long)client.getTag();
        handleRequest(clientPtr);
        return true;
    }

    @Keep
    public void flushFrontbufferFromNative(int drawableId, int framebuffer) {
        Drawable drawable = xServer.drawableManager.getDrawable(drawableId);
        if (drawable == null) return;

        synchronized (drawable.renderLock) {
            drawable.setData(null);
            Texture texture = drawable.getTexture();
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, framebuffer);
            texture.copyFromReadBuffer(drawable.width, drawable.height);
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER, 0);
        }

        Runnable onDrawListener = drawable.getOnDrawListener();
        if (onDrawListener != null) onDrawListener.run();
    }

    private long handleNewConnection(int fd) {
        return nativePeer.handleNewConnection(fd);
    }

    private void handleRequest(long clientPtr) {
        nativePeer.handleRequest(clientPtr);
    }

    private long getCurrentEGLContextPtr() {
        return nativePeer.getCurrentEGLContextPtr();
    }

    private void destroyClient(long clientPtr) {
        nativePeer.destroyClient(clientPtr);
    }

    private void destroyRenderer(long clientPtr) {
        nativePeer.destroyRenderer(clientPtr);
    }
}

