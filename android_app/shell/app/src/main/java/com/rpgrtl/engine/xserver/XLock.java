package com.rpgrtl.engine.xserver;

public interface XLock extends AutoCloseable {
    @Override
    void close();
}

