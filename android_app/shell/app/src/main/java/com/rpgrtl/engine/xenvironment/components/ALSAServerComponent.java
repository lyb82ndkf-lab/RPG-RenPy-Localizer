package com.rpgrtl.engine.xenvironment.components;

import com.rpgrtl.engine.alsaserver.ALSAClient;
import com.rpgrtl.engine.alsaserver.ALSAClientConnectionHandler;
import com.rpgrtl.engine.alsaserver.ALSARequestHandler;
import com.rpgrtl.engine.xconnector.UnixSocketConfig;
import com.rpgrtl.engine.xconnector.XConnectorEpoll;
import com.rpgrtl.engine.xenvironment.EnvironmentComponent;

public class ALSAServerComponent extends EnvironmentComponent {
    private XConnectorEpoll connector;
    private final UnixSocketConfig socketConfig;
    private final ALSAClient.Options options;

    public ALSAServerComponent(UnixSocketConfig socketConfig, ALSAClient.Options options) {
        this.socketConfig = socketConfig;
        this.options = options;
    }

    @Override
    public void start() {
        if (connector != null) return;
        ALSAClient.assignFramesPerBuffer(environment.getContext());
        connector = new XConnectorEpoll(socketConfig, new ALSAClientConnectionHandler(options), new ALSARequestHandler());
        connector.setMultithreadedClients(true);
        connector.start();
    }

    @Override
    public void stop() {
        if (connector != null) {
            connector.destroy();
            connector = null;
        }
    }
}

