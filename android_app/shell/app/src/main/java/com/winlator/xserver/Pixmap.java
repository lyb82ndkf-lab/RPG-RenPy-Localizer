package com.winlator.xserver;

import android.graphics.Bitmap;

import java.nio.ByteBuffer;

public final class Pixmap {
    static {
        System.loadLibrary("winlator");
    }

    private Pixmap() {}

    public static native void toBitmap(ByteBuffer colorData, ByteBuffer maskData, Bitmap bitmap);
}
