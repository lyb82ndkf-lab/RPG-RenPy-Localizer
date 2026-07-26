package com.rpgrtl.engine.widget;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.StateListDrawable;
import android.util.SparseIntArray;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import com.rpgrtl.engine.core.AppUtils;
import com.rpgrtl.engine.math.Mathf;
import com.rpgrtl.engine.winhandler.MouseEventFlags;
import com.rpgrtl.engine.winhandler.WinHandler;
import com.rpgrtl.engine.xserver.Pointer;
import com.rpgrtl.engine.xserver.XServer;
import com.rpgrtl.shell.ShellLog;

/**
 * Touch → X/Wine pointer bridge.
 *
 * <p>Modes via {@link #setMoveCursorToTouchpoint(boolean)}:
 * <ul>
 *   <li>true  = direct tap: finger = cursor, tap clicks at finger (hide OS cursor)</li>
 *   <li>false = pointer: swipe moves cursor, tap clicks at cursor (show cursor)</li>
 * </ul>
 *
 * <p>Pointer IDs from Android can be &gt;= 4; we map them to internal slots 0..MAX-1
 * instead of indexing by raw pointerId (which silently dropped all touches on some devices).
 */
public class TouchpadView extends View implements View.OnCapturedPointerListener {
    private static final int MAX_FINGERS = 10;
    private static final short MAX_TWO_FINGERS_SCROLL_DISTANCE = 350;
    public static final byte MAX_TAP_TRAVEL_DISTANCE = 12;
    public static final short MAX_TAP_MILLISECONDS = 280;
    public static final float CURSOR_ACCELERATION = 1.5f;
    public static final byte CURSOR_ACCELERATION_THRESHOLD = 6;

    private final Finger[] fingers = new Finger[MAX_FINGERS];
    /** Android pointerId → internal slot (0..MAX_FINGERS-1), -1 if free */
    private final SparseIntArray pointerSlots = new SparseIntArray();
    private int numFingers = 0;
    private float sensitivity = 1.0f;
    private Finger mouseMoveFinger = null;
    private boolean pointerButtonLeftEnabled = true;
    private boolean pointerButtonRightEnabled = true;
    private boolean moveCursorToTouchpoint = true;
    private Finger fingerPointerButtonLeft;
    private Finger fingerPointerButtonRight;
    private float scrollAccumY = 0;
    private boolean scrolling = false;
    private final XServer xServer;
    private Runnable fourFingersTapCallback;

    public TouchpadView(Context context, XServer xServer, boolean capturePointerOnExternalMouse) {
        super(context);
        this.xServer = xServer;
        setLayoutParams(new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setBackground(createTransparentBackground());
        setClickable(true);
        setFocusable(true);
        setFocusableInTouchMode(false);

        if (capturePointerOnExternalMouse) {
            setOnCapturedPointerListener(this);
            setOnClickListener(view -> requestPointerCapture());
        }
    }

    private static StateListDrawable createTransparentBackground() {
        StateListDrawable stateListDrawable = new StateListDrawable();
        stateListDrawable.addState(new int[]{android.R.attr.state_focused}, new ColorDrawable(Color.TRANSPARENT));
        stateListDrawable.addState(new int[0], new ColorDrawable(Color.TRANSPARENT));
        return stateListDrawable;
    }

    private int[] mapViewToScreen(float viewX, float viewY) {
        int vw = getWidth();
        int vh = getHeight();
        if (vw <= 0 || vh <= 0) {
            View parent = getParent() instanceof View ? (View) getParent() : null;
            if (parent != null && parent.getWidth() > 0 && parent.getHeight() > 0) {
                vw = parent.getWidth();
                vh = parent.getHeight();
            } else {
                vw = Math.max(1, AppUtils.getScreenWidth());
                vh = Math.max(1, AppUtils.getScreenHeight());
            }
        }
        int sw = Math.max(1, xServer.screenInfo.width);
        int sh = Math.max(1, xServer.screenInfo.height);
        int x = Mathf.clamp(Math.round(viewX * sw / (float) vw), 0, sw - 1);
        int y = Mathf.clamp(Math.round(viewY * sh / (float) vh), 0, sh - 1);
        return new int[]{x, y};
    }

    private int acquireSlot(int pointerId) {
        int existing = pointerSlots.get(pointerId, -1);
        if (existing >= 0) return existing;
        for (int i = 0; i < MAX_FINGERS; i++) {
            if (fingers[i] == null) {
                pointerSlots.put(pointerId, i);
                return i;
            }
        }
        return -1;
    }

    private int slotOf(int pointerId) {
        return pointerSlots.get(pointerId, -1);
    }

    private void releaseSlot(int pointerId) {
        int slot = pointerSlots.get(pointerId, -1);
        if (slot >= 0) {
            fingers[slot] = null;
            pointerSlots.delete(pointerId);
        }
    }

    private class Finger {
        private int x, y, startX, startY, lastX, lastY;
        private final long touchTime;
        private final float rawStartX, rawStartY;
        private float rawLastX, rawLastY;

        Finger(float viewX, float viewY) {
            int[] p = mapViewToScreen(viewX, viewY);
            x = startX = lastX = p[0];
            y = startY = lastY = p[1];
            rawStartX = rawLastX = viewX;
            rawStartY = rawLastY = viewY;
            touchTime = System.currentTimeMillis();
        }

        void update(float viewX, float viewY) {
            lastX = x;
            lastY = y;
            rawLastX = viewX;
            rawLastY = viewY;
            int[] p = mapViewToScreen(viewX, viewY);
            x = p[0];
            y = p[1];
        }

        int deltaX() {
            float dx = (x - lastX) * sensitivity;
            if (Math.abs(dx) > CURSOR_ACCELERATION_THRESHOLD) dx *= CURSOR_ACCELERATION;
            return Mathf.roundPoint(dx);
        }

        int deltaY() {
            float dy = (y - lastY) * sensitivity;
            if (Math.abs(dy) > CURSOR_ACCELERATION_THRESHOLD) dy *= CURSOR_ACCELERATION;
            return Mathf.roundPoint(dy);
        }

        boolean isTap() {
            float travel = (float) Math.hypot(rawLastX - rawStartX, rawLastY - rawStartY);
            float maxPx = MAX_TAP_TRAVEL_DISTANCE * getResources().getDisplayMetrics().density;
            return (System.currentTimeMillis() - touchTime) < MAX_TAP_MILLISECONDS && travel < maxPx;
        }

        float travelDistance() {
            return (float) Math.hypot(x - startX, y - startY);
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        final int actionMasked = event.getActionMasked();
        // Log FIRST — previous builds logged after inject, so crashes looked like "never entered".
        if (actionMasked == MotionEvent.ACTION_DOWN || actionMasked == MotionEvent.ACTION_POINTER_DOWN) {
            try {
                ShellLog.INSTANCE.info(getContext(),
                    "Touchpad ENTER action=" + actionMasked
                        + " xy=" + (int) event.getX() + "," + (int) event.getY()
                        + " count=" + event.getPointerCount()
                        + " mode=" + (moveCursorToTouchpoint ? "direct" : "pointer")
                        + " enabled=" + isEnabled()
                        + " view=" + getWidth() + "x" + getHeight());
            } catch (Throwable ignored) {}
        }

        try {
            return onTouchEventInner(event);
        } catch (Throwable error) {
            try {
                ShellLog.INSTANCE.error(getContext(), "Touchpad onTouchEvent crashed", error);
            } catch (Throwable ignored) {}
            return true;
        }
    }

    private boolean onTouchEventInner(MotionEvent event) {
        if (isMouseSource(event)) {
            return onExternalMouseEvent(event);
        }

        int actionIndex = event.getActionIndex();
        int pointerId = event.getPointerId(actionIndex);
        int actionMasked = event.getActionMasked();

        switch (actionMasked) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN: {
                scrollAccumY = 0;
                scrolling = false;
                int slot = acquireSlot(pointerId);
                if (slot < 0) {
                    ShellLog.INSTANCE.info(getContext(), "Touchpad DROP no free slot pid=" + pointerId);
                    return true;
                }
                fingers[slot] = new Finger(event.getX(actionIndex), event.getY(actionIndex));
                numFingers++;
                ShellLog.INSTANCE.info(getContext(),
                    "Touchpad DOWN mode=" + (moveCursorToTouchpoint ? "direct" : "pointer")
                        + " pid=" + pointerId + " slot=" + slot
                        + " at=" + fingers[slot].x + "," + fingers[slot].y
                        + " screen=" + xServer.screenInfo.width + "x" + xServer.screenInfo.height
                        + " view=" + getWidth() + "x" + getHeight()
                        + " enabled=" + isEnabled()
                        + " leftClick=" + pointerButtonLeftEnabled);
                if (isEnabled() && moveCursorToTouchpoint && numFingers == 1) {
                    injectMoveAbsolute(fingers[slot].x, fingers[slot].y);
                }
                break;
            }
            case MotionEvent.ACTION_MOVE: {
                for (int i = 0; i < event.getPointerCount(); i++) {
                    int pid = event.getPointerId(i);
                    int slot = slotOf(pid);
                    if (slot < 0 || fingers[slot] == null) continue;
                    fingers[slot].update(event.getX(i), event.getY(i));
                    handleFingerMove(fingers[slot]);
                }
                break;
            }
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP: {
                int slot = slotOf(pointerId);
                if (slot >= 0 && fingers[slot] != null) {
                    fingers[slot].update(event.getX(actionIndex), event.getY(actionIndex));
                    handleFingerUp(fingers[slot]);
                    releaseSlot(pointerId);
                    numFingers = Math.max(0, numFingers - 1);
                }
                break;
            }
            case MotionEvent.ACTION_CANCEL: {
                for (int i = 0; i < MAX_FINGERS; i++) fingers[i] = null;
                pointerSlots.clear();
                numFingers = 0;
                if (xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_LEFT)) {
                    injectButton(Pointer.Button.BUTTON_LEFT, false);
                }
                fingerPointerButtonLeft = null;
                fingerPointerButtonRight = null;
                break;
            }
        }
        return true;
    }

    private static boolean isMouseSource(MotionEvent event) {
        int sources = event.getSource();
        return (sources & InputDevice.SOURCE_MOUSE) == InputDevice.SOURCE_MOUSE
            || (sources & InputDevice.SOURCE_MOUSE_RELATIVE) == InputDevice.SOURCE_MOUSE_RELATIVE
            || event.getToolType(0) == MotionEvent.TOOL_TYPE_MOUSE;
    }

    private void injectMoveAbsolute(int x, int y) {
        try {
            int sw = Math.max(1, xServer.screenInfo.width);
            int sh = Math.max(1, xServer.screenInfo.height);
            x = Mathf.clamp(x, 0, sw - 1);
            y = Mathf.clamp(y, 0, sh - 1);
            WinHandler winHandler = xServer.getWinHandler();
            if (xServer.isRelativeMouseMovement()) {
                int dx = x - xServer.pointer.getX();
                int dy = y - xServer.pointer.getY();
                if (winHandler != null) winHandler.mouseEvent(MouseEventFlags.MOVE, dx, dy, 0);
                xServer.moveVisualPointerDelta(dx, dy);
            } else {
                xServer.injectPointerMove(x, y);
                if (winHandler != null) {
                    try {
                        winHandler.mouseEventAbsolute(MouseEventFlags.MOVE, x, y, 0);
                    } catch (Throwable ignored) {
                        // Win32 path optional until guest is ready.
                    }
                }
            }
        } catch (Throwable error) {
            try {
                ShellLog.INSTANCE.error(getContext(), "injectMoveAbsolute failed x=" + x + " y=" + y, error);
            } catch (Throwable ignored) {}
        }
    }

    private void injectMoveDelta(int dx, int dy) {
        if (dx == 0 && dy == 0) return;
        try {
            WinHandler winHandler = xServer.getWinHandler();
            if (xServer.isRelativeMouseMovement()) {
                if (winHandler != null) winHandler.mouseEvent(MouseEventFlags.MOVE, dx, dy, 0);
                xServer.moveVisualPointerDelta(dx, dy);
            } else {
                xServer.injectPointerMoveDelta(dx, dy);
                if (winHandler != null) {
                    try {
                        winHandler.mouseEventAbsolute(
                            MouseEventFlags.MOVE,
                            xServer.pointer.getX(),
                            xServer.pointer.getY(),
                            0
                        );
                    } catch (Throwable ignored) {}
                }
            }
        } catch (Throwable error) {
            try {
                ShellLog.INSTANCE.error(getContext(), "injectMoveDelta failed", error);
            } catch (Throwable ignored) {}
        }
    }

    private void injectButton(Pointer.Button button, boolean down) {
        try {
            WinHandler winHandler = xServer.getWinHandler();
            if (xServer.isRelativeMouseMovement()) {
                if (winHandler != null) {
                    winHandler.mouseEvent(MouseEventFlags.getFlagFor(button, down), 0, 0, 0);
                }
                return;
            }
            if (down) xServer.injectPointerButtonPress(button);
            else xServer.injectPointerButtonRelease(button);
            if (winHandler != null) {
                try {
                    int flags = MouseEventFlags.getFlagFor(button, down);
                    if (button == Pointer.Button.BUTTON_SCROLL_UP) {
                        winHandler.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), 120);
                    } else if (button == Pointer.Button.BUTTON_SCROLL_DOWN) {
                        winHandler.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), -120);
                    } else {
                        winHandler.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), 0);
                    }
                } catch (Throwable ignored) {}
            }
        } catch (Throwable error) {
            try {
                ShellLog.INSTANCE.error(getContext(), "injectButton failed " + button + " down=" + down, error);
            } catch (Throwable ignored) {}
        }
    }

    private void handleFingerUp(Finger finger1) {
        // numFingers is still the count including this finger until caller decrements
        int active = 0;
        for (Finger f : fingers) if (f != null) active++;

        if (active == 1) {
            if (finger1.isTap() && pointerButtonLeftEnabled) {
                if (moveCursorToTouchpoint) {
                    injectMoveAbsolute(finger1.x, finger1.y);
                }
                ShellLog.INSTANCE.info(getContext(),
                    "Touchpad TAP mode=" + (moveCursorToTouchpoint ? "direct" : "pointer")
                        + " clickAt=" + xServer.pointer.getX() + "," + xServer.pointer.getY()
                        + (moveCursorToTouchpoint ? (" finger=" + finger1.x + "," + finger1.y) : ""));
                pressPointerButtonLeft(finger1);
            }
        } else if (active == 2) {
            Finger finger2 = findSecondFinger(finger1);
            if (finger2 != null && finger1.isTap()) pressPointerButtonRight(finger1);
        } else if (active == 4 && fourFingersTapCallback != null) {
            boolean allTap = true;
            for (Finger f : fingers) {
                if (f != null && !f.isTap()) {
                    allTap = false;
                    break;
                }
            }
            if (allTap) fourFingersTapCallback.run();
        }
        releasePointerButtonLeft(finger1);
        releasePointerButtonRight(finger1);
    }

    private void handleFingerMove(Finger finger1) {
        if (!isEnabled()) return;
        boolean skipPointerMove = false;

        int active = 0;
        for (Finger f : fingers) if (f != null) active++;

        Finger finger2 = active == 2 ? findSecondFinger(finger1) : null;
        if (finger2 != null) {
            final float resolutionScale = 1000.0f / Math.min(xServer.screenInfo.width, xServer.screenInfo.height);
            float currDistance = (float) Math.hypot(finger1.x - finger2.x, finger1.y - finger2.y) * resolutionScale;

            if (currDistance < MAX_TWO_FINGERS_SCROLL_DISTANCE) {
                scrollAccumY += ((finger1.y + finger2.y) * 0.5f) - (finger1.lastY + finger2.lastY) * 0.5f;
                if (scrollAccumY < -100) {
                    injectButton(Pointer.Button.BUTTON_SCROLL_DOWN, true);
                    injectButton(Pointer.Button.BUTTON_SCROLL_DOWN, false);
                    scrollAccumY = 0;
                } else if (scrollAccumY > 100) {
                    injectButton(Pointer.Button.BUTTON_SCROLL_UP, true);
                    injectButton(Pointer.Button.BUTTON_SCROLL_UP, false);
                    scrollAccumY = 0;
                }
                scrolling = true;
            } else if (currDistance >= MAX_TWO_FINGERS_SCROLL_DISTANCE
                && !xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_LEFT)
                && finger2.travelDistance() < MAX_TAP_TRAVEL_DISTANCE) {
                pressPointerButtonLeft(finger1);
                skipPointerMove = true;
            }
        }

        if (!scrolling && active <= 2 && !skipPointerMove && active >= 1) {
            if (moveCursorToTouchpoint && active == 1) {
                injectMoveAbsolute(finger1.x, finger1.y);
            } else if (!moveCursorToTouchpoint && active == 1) {
                injectMoveDelta(finger1.deltaX(), finger1.deltaY());
            }
        }
    }

    public void mouseMove(float x, float y, int action) {
        switch (action) {
            case MotionEvent.ACTION_DOWN:
                mouseMoveFinger = new Finger(x, y);
                break;
            case MotionEvent.ACTION_MOVE:
                if (mouseMoveFinger != null) {
                    mouseMoveFinger.update(x, y);
                    handleFingerMove(mouseMoveFinger);
                }
                break;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                mouseMoveFinger = null;
                break;
        }
    }

    private Finger findSecondFinger(Finger finger) {
        for (Finger f : fingers) {
            if (f != null && f != finger) return f;
        }
        return null;
    }

    private void pressPointerButtonLeft(Finger finger) {
        if (isEnabled() && pointerButtonLeftEnabled && !xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_LEFT)) {
            injectButton(Pointer.Button.BUTTON_LEFT, true);
            fingerPointerButtonLeft = finger;
        }
    }

    private void pressPointerButtonRight(Finger finger) {
        if (isEnabled() && pointerButtonRightEnabled && !xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_RIGHT)) {
            injectButton(Pointer.Button.BUTTON_RIGHT, true);
            fingerPointerButtonRight = finger;
        }
    }

    private void releasePointerButtonLeft(final Finger finger) {
        if (isEnabled() && finger == fingerPointerButtonLeft && xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_LEFT)) {
            postDelayed(() -> {
                injectButton(Pointer.Button.BUTTON_LEFT, false);
                fingerPointerButtonLeft = null;
            }, 30);
        }
    }

    private void releasePointerButtonRight(final Finger finger) {
        if (isEnabled() && finger == fingerPointerButtonRight && xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_RIGHT)) {
            postDelayed(() -> {
                injectButton(Pointer.Button.BUTTON_RIGHT, false);
                fingerPointerButtonRight = null;
            }, 30);
        }
    }

    public void setSensitivity(float sensitivity) {
        this.sensitivity = sensitivity;
    }

    public boolean isPointerButtonLeftEnabled() {
        return pointerButtonLeftEnabled;
    }

    public void setPointerButtonLeftEnabled(boolean pointerButtonLeftEnabled) {
        this.pointerButtonLeftEnabled = pointerButtonLeftEnabled;
    }

    public boolean isPointerButtonRightEnabled() {
        return pointerButtonRightEnabled;
    }

    public void setPointerButtonRightEnabled(boolean pointerButtonRightEnabled) {
        this.pointerButtonRightEnabled = pointerButtonRightEnabled;
    }

    public void setFourFingersTapCallback(Runnable fourFingersTapCallback) {
        this.fourFingersTapCallback = fourFingersTapCallback;
    }

    public boolean isMoveCursorToTouchpoint() {
        return moveCursorToTouchpoint;
    }

    public void setMoveCursorToTouchpoint(boolean moveCursorToTouchpoint) {
        this.moveCursorToTouchpoint = moveCursorToTouchpoint;
    }

    public boolean onExternalMouseEvent(MotionEvent event) {
        if (!isEnabled()) return false;

        int action = event.getActionMasked();
        int actionButton = event.getActionButton();

        switch (action) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_BUTTON_PRESS: {
                int[] p = mapViewToScreen(event.getX(), event.getY());
                injectMoveAbsolute(p[0], p[1]);
                int btn = actionButton != 0 ? actionButton : event.getButtonState();
                if ((btn & MotionEvent.BUTTON_PRIMARY) != 0 || action == MotionEvent.ACTION_DOWN) {
                    injectButton(Pointer.Button.BUTTON_LEFT, true);
                }
                if ((btn & MotionEvent.BUTTON_SECONDARY) != 0) {
                    injectButton(Pointer.Button.BUTTON_RIGHT, true);
                }
                return true;
            }
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_BUTTON_RELEASE: {
                int btn = actionButton != 0 ? actionButton : MotionEvent.BUTTON_PRIMARY;
                if ((btn & MotionEvent.BUTTON_PRIMARY) != 0 || action == MotionEvent.ACTION_UP) {
                    if (xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_LEFT)) {
                        injectButton(Pointer.Button.BUTTON_LEFT, false);
                    }
                }
                if ((btn & MotionEvent.BUTTON_SECONDARY) != 0) {
                    if (xServer.pointer.isButtonPressed(Pointer.Button.BUTTON_RIGHT)) {
                        injectButton(Pointer.Button.BUTTON_RIGHT, false);
                    }
                }
                return true;
            }
            case MotionEvent.ACTION_MOVE:
            case MotionEvent.ACTION_HOVER_MOVE: {
                int[] p = mapViewToScreen(event.getX(), event.getY());
                injectMoveAbsolute(p[0], p[1]);
                return true;
            }
            case MotionEvent.ACTION_SCROLL: {
                float scrollY = event.getAxisValue(MotionEvent.AXIS_VSCROLL);
                if (scrollY <= -1.0f) {
                    injectButton(Pointer.Button.BUTTON_SCROLL_DOWN, true);
                    injectButton(Pointer.Button.BUTTON_SCROLL_DOWN, false);
                } else if (scrollY >= 1.0f) {
                    injectButton(Pointer.Button.BUTTON_SCROLL_UP, true);
                    injectButton(Pointer.Button.BUTTON_SCROLL_UP, false);
                }
                return true;
            }
            default:
                return false;
        }
    }

    public float[] computeDeltaPoint(float lastX, float lastY, float x, float y) {
        int[] a = mapViewToScreen(lastX, lastY);
        int[] b = mapViewToScreen(x, y);
        return new float[]{b[0] - a[0], b[1] - a[1]};
    }

    @Override
    public boolean onCapturedPointer(View view, MotionEvent event) {
        if (event.getAction() == MotionEvent.ACTION_MOVE) {
            float dx = event.getX() * sensitivity;
            if (Math.abs(dx) > CURSOR_ACCELERATION_THRESHOLD) dx *= CURSOR_ACCELERATION;
            float dy = event.getY() * sensitivity;
            if (Math.abs(dy) > CURSOR_ACCELERATION_THRESHOLD) dy *= CURSOR_ACCELERATION;
            injectMoveDelta(Mathf.roundPoint(dx), Mathf.roundPoint(dy));
            return true;
        }
        event.setSource(event.getSource() | InputDevice.SOURCE_MOUSE);
        return onExternalMouseEvent(event);
    }
}
