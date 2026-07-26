package com.winlator.xserver;

import android.graphics.Bitmap;

import java.nio.ByteBuffer;

public final class Drawable {
    static {
        System.loadLibrary("winlator");
    }

    private Drawable() {}

    public static native void drawBitmap(short width, short height, ByteBuffer srcData, ByteBuffer dstData);
    public static native void drawAlphaMaskedBitmap(byte foreRed, byte foreGreen, byte foreBlue, byte backRed, byte backGreen, byte backBlue, ByteBuffer srcData, ByteBuffer maskData, ByteBuffer dstData);
    public static native void copyArea(short srcX, short srcY, short dstX, short dstY, short width, short height, short srcStride, short dstStride, ByteBuffer srcData, ByteBuffer dstData);
    public static native void copyAreaOp(short srcX, short srcY, short dstX, short dstY, short width, short height, short srcStride, short dstStride, ByteBuffer srcData, ByteBuffer dstData, int gcFunction);
    public static native void fillRect(short x, short y, short width, short height, int color, short stride, ByteBuffer data);
    public static native void drawLine(short x0, short y0, short x1, short y1, int color, short lineWidth, short stride, ByteBuffer data);
    public static native void fromBitmap(Bitmap bitmap, ByteBuffer data);
}
