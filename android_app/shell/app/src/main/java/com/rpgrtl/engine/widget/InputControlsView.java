package com.rpgrtl.engine.widget;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.Point;
import android.graphics.PointF;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;

import com.rpgrtl.engine.inputcontrols.Binding;
import com.rpgrtl.engine.inputcontrols.ControlElement;
import com.rpgrtl.engine.inputcontrols.ControlsProfile;
import com.rpgrtl.engine.inputcontrols.ExternalController;
import com.rpgrtl.engine.inputcontrols.ExternalControllerBinding;
import com.rpgrtl.engine.inputcontrols.GamepadState;
import com.rpgrtl.engine.math.Mathf;
import com.rpgrtl.engine.winhandler.MouseEventFlags;
import com.rpgrtl.engine.winhandler.WinHandler;
import com.rpgrtl.engine.xserver.Pointer;
import com.rpgrtl.engine.xserver.XServer;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Timer;
import java.util.TimerTask;

public class InputControlsView extends View {
    public static final float DEFAULT_OVERLAY_OPACITY = 0.4f;
    private boolean editMode = false;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private ColorFilter lightColorFilter;
    private ColorFilter darkColorFilter;
    private final Point cursor = new Point();
    private boolean readyToDraw = false;
    private boolean moveCursor = false;
    private boolean moveElement = false;
    private int snappingSize;
    private float startX;
    private float startY;
    private float offsetX;
    private float offsetY;
    private ControlElement selectedElement;
    private ControlsProfile profile;
    private float overlayOpacity = DEFAULT_OVERLAY_OPACITY;
    private TouchpadView touchpadView;
    private XServer xServer;
    private final Bitmap[] icons = new Bitmap[18];
    private Timer mouseMoveTimer;
    private final PointF mouseMoveOffset = new PointF();
    private boolean showTouchscreenControls = true;

    public InputControlsView(Context context) {
        super(context);
        setClickable(true);
        setFocusable(true);
        setFocusableInTouchMode(true);
        setBackgroundColor(0x00000000);
        setLayoutParams(new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    public void setEditMode(boolean editMode) {
        this.editMode = editMode;
        invalidate();
    }

    public boolean isEditMode() {
        return editMode;
    }

    public void setOverlayOpacity(float overlayOpacity) {
        this.overlayOpacity = overlayOpacity;
    }

    public float getOverlayOpacity() {
        return overlayOpacity;
    }

    public int getSnappingSize() {
        return snappingSize;
    }

    @Override
    protected synchronized void onDraw(Canvas canvas) {
        int width = getWidth();
        int height = getHeight();

        if (width == 0 || height == 0) {
            readyToDraw = false;
            return;
        }

        snappingSize = width / 100;
        readyToDraw = true;

        if (editMode) {
            drawGrid(canvas);
            drawCursor(canvas);
        }

        if (profile != null) {
            if (!profile.isElementsLoaded()) profile.loadElements(this);
            List<ControlElement> elements = profile.getElements();
            if (touchpadView != null && elements.isEmpty()) touchpadView.setPointerButtonRightEnabled(true);
            if (showTouchscreenControls) for (ControlElement element : elements) element.draw(canvas);
        }

        super.onDraw(canvas);
    }

    private void drawGrid(Canvas canvas) {
        paint.setStyle(Paint.Style.FILL);
        paint.setStrokeWidth(snappingSize * 0.0625f);
        paint.setColor(0xff000000);
        canvas.drawColor(0x66000000);

        paint.setAntiAlias(false);
        paint.setColor(0xff303030);

        int width = getMaxWidth();
        int height = getMaxHeight();

        for (int i = 0; i < width; i += snappingSize) {
            canvas.drawLine(i, 0, i, height, paint);
            canvas.drawLine(0, i, width, i, paint);
        }

        float cx = Mathf.roundTo(width * 0.5f, snappingSize);
        float cy = Mathf.roundTo(height * 0.5f, snappingSize);
        paint.setColor(0xff424242);

        for (int i = 0; i < width; i += snappingSize * 2) {
            canvas.drawLine(cx, i, cx, i + snappingSize, paint);
            canvas.drawLine(i, cy, i + snappingSize, cy, paint);
        }

        paint.setAntiAlias(true);
    }

    private void drawCursor(Canvas canvas) {
        paint.setStyle(Paint.Style.FILL);
        paint.setStrokeWidth(snappingSize * 0.0625f);
        paint.setColor(0xffc62828);

        paint.setAntiAlias(false);
        canvas.drawLine(0, cursor.y, getMaxWidth(), cursor.y, paint);
        canvas.drawLine(cursor.x, 0, cursor.x, getMaxHeight(), paint);

        paint.setAntiAlias(true);
    }

    public synchronized boolean addElement() {
        if (editMode && profile != null) {
            ControlElement element = new ControlElement(this);
            element.setX(cursor.x);
            element.setY(cursor.y);
            profile.addElement(element);
            profile.save();
            selectElement(element);
            return true;
        }
        else return false;
    }

    public synchronized ControlElement addElementAt(int x, int y, ControlElement.Type type) {
        if (!editMode || profile == null) return null;
        ControlElement element = new ControlElement(this);
        element.setType(type);
        element.setX(x);
        element.setY(y);
        profile.addElement(element);
        profile.save();
        selectElement(element);
        return element;
    }

    public synchronized boolean removeElement() {
        if (editMode && selectedElement != null && profile != null) {
            profile.removeElement(selectedElement);
            selectedElement = null;
            profile.save();
            invalidate();
            return true;
        }
        else return false;
    }

    public ControlElement getSelectedElement() {
        return selectedElement;
    }

    private synchronized void deselectAllElements() {
        selectedElement = null;
        if (profile != null) {
            for (ControlElement element : profile.getElements()) element.setSelected(false);
        }
    }

    private void selectElement(ControlElement element) {
        deselectAllElements();
        if (element != null) {
            selectedElement = element;
            selectedElement.setSelected(true);
        }
        invalidate();
    }

    public synchronized ControlsProfile getProfile() {
        return profile;
    }

    public synchronized void setProfile(ControlsProfile profile) {
        if (profile != null) {
            this.profile = profile;
            deselectAllElements();
        }
        else this.profile = null;
    }

    public boolean isShowTouchscreenControls() {
        return showTouchscreenControls;
    }

    public void setShowTouchscreenControls(boolean showTouchscreenControls) {
        this.showTouchscreenControls = showTouchscreenControls;
    }

    private synchronized ControlElement intersectElement(float x, float y) {
        if (profile != null) {
            for (ControlElement element : profile.getElements()) {
                if (element.containsPoint(x, y)) return element;
            }
        }
        return null;
    }

    public Paint getPaint() {
        return paint;
    }

    public ColorFilter getLightColorFilter() {
        if (lightColorFilter == null) lightColorFilter = new PorterDuffColorFilter(0xffffffff, PorterDuff.Mode.SRC_IN);
        return lightColorFilter;
    }

    public ColorFilter getDarkColorFilter() {
        if (darkColorFilter == null) darkColorFilter = new PorterDuffColorFilter(0xff000000, PorterDuff.Mode.SRC_IN);
        return darkColorFilter;
    }

    public TouchpadView getTouchpadView() {
        return touchpadView;
    }

    public void setTouchpadView(TouchpadView touchpadView) {
        this.touchpadView = touchpadView;
    }

    public XServer getXServer() {
        return xServer;
    }

    public void setXServer(XServer xServer) {
        this.xServer = xServer;
        createMouseMoveTimer();
    }

    public int getMaxWidth() {
        return (int)Mathf.roundTo(getWidth(), snappingSize);
    }

    public int getMaxHeight() {
        return (int)Mathf.roundTo(getHeight(), snappingSize);
    }

    private void createMouseMoveTimer() {
        if (profile != null && mouseMoveTimer == null && xServer != null) {
            final float cursorSpeed = profile.getCursorSpeed();
            mouseMoveTimer = new Timer();
            mouseMoveTimer.schedule(new TimerTask() {
                @Override
                public void run() {
                    int dx = (int)(mouseMoveOffset.x * 10 * cursorSpeed);
                    int dy = (int)(mouseMoveOffset.y * 10 * cursorSpeed);
                    if (dx == 0 && dy == 0) return;
                    if (xServer.isRelativeMouseMovement() && xServer.getWinHandler() != null) {
                        xServer.getWinHandler().mouseEvent(
                            com.rpgrtl.engine.winhandler.MouseEventFlags.MOVE, dx, dy, 0);
                        xServer.moveVisualPointerDelta(dx, dy);
                    } else {
                        xServer.injectPointerMoveDelta(dx, dy);
                    }
                }
            }, 0, 1000 / 60);
        }
    }

    private void processJoystickInput(ExternalController controller) {
        ExternalControllerBinding controllerBinding;
        final int[] axes = {MotionEvent.AXIS_X, MotionEvent.AXIS_Y, MotionEvent.AXIS_Z, MotionEvent.AXIS_RZ, MotionEvent.AXIS_HAT_X, MotionEvent.AXIS_HAT_Y};
        GamepadState state = controller.getGamepadState();
        final float[] values = {state.thumbLX, state.thumbLY, state.thumbRX, state.thumbRY, state.getDPadX(), state.getDPadY()};

        for (byte i = 0; i < axes.length; i++) {
            if (Math.abs(values[i]) > ControlElement.STICK_DEAD_ZONE) {
                controllerBinding = controller.getControllerBinding(ExternalControllerBinding.getKeyCodeForAxis(axes[i], Mathf.sign(values[i])));
                if (controllerBinding != null) handleInputEvent(controllerBinding.getBinding(), true, values[i]);
            }
            else {
                controllerBinding = controller.getControllerBinding(ExternalControllerBinding.getKeyCodeForAxis(axes[i], (byte) 1));
                if (controllerBinding != null) handleInputEvent(controllerBinding.getBinding(), false, values[i]);
                controllerBinding = controller.getControllerBinding(ExternalControllerBinding.getKeyCodeForAxis(axes[i], (byte)-1));
                if (controllerBinding != null) handleInputEvent(controllerBinding.getBinding(), false, values[i]);
            }
        }
    }

    @Override
    public boolean onGenericMotionEvent(MotionEvent event) {
        if (!editMode && profile != null) {
            ExternalController controller = profile.getController(event.getDeviceId());
            if (controller != null && controller.updateStateFromMotionEvent(event)) {
                GamepadState state = controller.getGamepadState();
                ExternalControllerBinding controllerBinding;
                controllerBinding = controller.getControllerBinding(KeyEvent.KEYCODE_BUTTON_L2);
                if (controllerBinding != null) handleInputEvent(controllerBinding.getBinding(), state.isPressed(ExternalController.IDX_BUTTON_L2));

                controllerBinding = controller.getControllerBinding(KeyEvent.KEYCODE_BUTTON_R2);
                if (controllerBinding != null) handleInputEvent(controllerBinding.getBinding(), state.isPressed(ExternalController.IDX_BUTTON_R2));

                processJoystickInput(controller);
                return true;
            }
        }
        return super.onGenericMotionEvent(event);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        int actionMasked = event.getActionMasked();
        if (actionMasked == MotionEvent.ACTION_DOWN) {
            // Always log entry so runtime log proves this view received the event.
            try {
                boolean loaded = profile != null && profile.isElementsLoaded();
                int count = loaded ? profile.getElements().size() : -1;
                com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(),
                    "InputControls touch DOWN editMode=" + editMode
                        + " profile=" + (profile != null)
                        + " elementsLoaded=" + loaded
                        + " elements=" + count
                        + " touchpadNull=" + (touchpadView == null)
                        + " showControls=" + showTouchscreenControls
                        + " xy=" + (int) event.getX() + "," + (int) event.getY()
                        + " size=" + getWidth() + "x" + getHeight());
            } catch (Throwable ignored) {}
        }

        if (editMode && readyToDraw) {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN: {
                    startX = event.getX();
                    startY = event.getY();

                    ControlElement element = intersectElement(startX, startY);
                    moveCursor = true;
                    moveElement = false;
                    if (element != null) {
                        offsetX = startX - element.getX();
                        offsetY = startY - element.getY();
                        moveCursor = false;
                    }

                    selectElement(element);
                    break;
                }
                case MotionEvent.ACTION_MOVE: {
                    if (selectedElement != null) {
                        float dx = Math.abs(event.getX() - startX);
                        float dy = Math.abs(event.getY() - startY);

                        if (dx >= TouchpadView.MAX_TAP_TRAVEL_DISTANCE || dy >= TouchpadView.MAX_TAP_TRAVEL_DISTANCE) moveElement = true;

                        if (moveElement) {
                            selectedElement.setX((int)Mathf.roundTo(event.getX() - offsetX, snappingSize));
                            selectedElement.setY((int)Mathf.roundTo(event.getY() - offsetY, snappingSize));
                            invalidate();
                        }
                    }
                    break;
                }
                case MotionEvent.ACTION_UP: {
                    if (selectedElement != null && profile != null && moveElement) profile.save();
                    if (moveCursor) cursor.set((int)Mathf.roundTo(event.getX(), snappingSize), (int)Mathf.roundTo(event.getY(), snappingSize));
                    invalidate();
                    break;
                }
            }
            return true;
        }

        // Physical mouse must never be swallowed by virtual-key hit tests.
        int sources = event.getSource();
        boolean mouseLike = (sources & android.view.InputDevice.SOURCE_MOUSE) == android.view.InputDevice.SOURCE_MOUSE
            || (sources & android.view.InputDevice.SOURCE_MOUSE_RELATIVE) == android.view.InputDevice.SOURCE_MOUSE_RELATIVE
            || event.getToolType(0) == MotionEvent.TOOL_TYPE_MOUSE;
        if (mouseLike) {
            if (touchpadView != null) touchpadView.onExternalMouseEvent(event);
            return true;
        }

        int actionIndex = event.getActionIndex();
        int pointerId = event.getPointerId(actionIndex);
        boolean handled = false;
        // Lazy-load profile elements if set but not yet drawn.
        if (profile != null && !profile.isElementsLoaded() && getWidth() > 0 && getHeight() > 0) {
            try {
                profile.loadElements(this);
            } catch (Throwable error) {
                try {
                    com.rpgrtl.shell.ShellLog.INSTANCE.error(getContext(), "loadElements failed", error);
                } catch (Throwable ignored) {}
            }
        }
        boolean elementsReady = profile != null && profile.isElementsLoaded()
            && showTouchscreenControls && !profile.getElements().isEmpty();

        switch (actionMasked) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_POINTER_DOWN: {
                float x = event.getX(actionIndex);
                float y = event.getY(actionIndex);

                if (touchpadView != null) touchpadView.setPointerButtonLeftEnabled(true);
                if (elementsReady) {
                    for (ControlElement element : profile.getElements()) {
                        if (!element.containsPoint(x, y)) continue;
                        if (element.handleTouchDown(pointerId, x, y)) {
                            handled = true;
                            if (touchpadView != null
                                    && element.getBindingAt(0) == Binding.MOUSE_LEFT_BUTTON
                                    && element.getLastBindingIndex() == 0) {
                                touchpadView.setPointerButtonLeftEnabled(false);
                            }
                            break;
                        }
                    }
                }
                // Blank area / no virtual keys → full-screen mouse (ALWAYS).
                if (!handled) {
                    if (touchpadView != null) touchpadView.setPointerButtonLeftEnabled(true);
                    forwardToTouchpad(event, "DOWN");
                } else if (actionMasked == MotionEvent.ACTION_DOWN) {
                    try {
                        Binding b = Binding.NONE;
                        if (elementsReady) {
                            for (ControlElement element : profile.getElements()) {
                                if (element.containsPoint(x, y)) {
                                    b = element.getBindingAt(0);
                                    break;
                                }
                            }
                        }
                        com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(),
                            "InputControls virtual-key consumed touch at " + (int) x + "," + (int) y
                                + " binding=" + b
                                + " xServerNull=" + (xServer == null));
                    } catch (Throwable ignored) {}
                }
                break;
            }
            case MotionEvent.ACTION_MOVE: {
                boolean needsTouchpad = !elementsReady;
                if (elementsReady) {
                    for (int i = 0, count = event.getPointerCount(); i < count; i++) {
                        float x = event.getX(i);
                        float y = event.getY(i);
                        int pid = event.getPointerId(i);
                        boolean fingerHandled = false;
                        for (ControlElement element : profile.getElements()) {
                            if (element.handleTouchMove(pid, x, y)) {
                                fingerHandled = true;
                            }
                        }
                        if (!fingerHandled) needsTouchpad = true;
                    }
                }
                // When no virtual keys, always forward MOVE (pointer-mode swipes).
                if (needsTouchpad || !elementsReady) forwardToTouchpad(event, "MOVE");
                break;
            }
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_POINTER_UP:
            case MotionEvent.ACTION_CANCEL: {
                float x = event.getX(actionIndex);
                float y = event.getY(actionIndex);
                if (elementsReady) {
                    for (ControlElement element : profile.getElements()) {
                        if (element.handleTouchUp(pointerId, x, y)) handled = true;
                    }
                }
                if (!handled || actionMasked == MotionEvent.ACTION_CANCEL) {
                    forwardToTouchpad(event, actionMasked == MotionEvent.ACTION_CANCEL ? "CANCEL" : "UP");
                }
                if (actionMasked != MotionEvent.ACTION_CANCEL && touchpadView != null) {
                    touchpadView.setPointerButtonLeftEnabled(true);
                }
                break;
            }
        }
        return true;
    }

    private void forwardToTouchpad(MotionEvent event, String tag) {
        if (touchpadView == null) {
            try {
                com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(), "forward→Touchpad SKIP null tag=" + tag);
            } catch (Throwable ignored) {}
            return;
        }
        try {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(),
                    "forward→Touchpad " + tag
                        + " xy=" + (int) event.getX() + "," + (int) event.getY()
                        + " enabled=" + touchpadView.isEnabled());
            }
            touchpadView.setEnabled(true);
            touchpadView.onTouchEvent(event);
        } catch (Throwable error) {
            try {
                com.rpgrtl.shell.ShellLog.INSTANCE.error(getContext(), "forward→Touchpad FAILED " + tag, error);
            } catch (Throwable ignored) {}
        }
    }

    public boolean onKeyEvent(KeyEvent event) {
        if (profile != null && event.getRepeatCount() == 0) {
            ExternalController controller = profile.getController(event.getDeviceId());
            if (controller != null) {
                ExternalControllerBinding controllerBinding = controller.getControllerBinding(event.getKeyCode());
                if (controllerBinding != null) {
                    int action = event.getAction();

                    if (action == KeyEvent.ACTION_DOWN) {
                        handleInputEvent(controllerBinding.getBinding(), true);
                    }
                    else if (action == KeyEvent.ACTION_UP) {
                        handleInputEvent(controllerBinding.getBinding(), false);
                    }
                    return true;
                }
            }
        }
        return false;
    }

    public void handleInputEvent(Binding[] bindings, boolean isActionDown) {
        for (Binding binding : bindings) {
            if (binding != Binding.NONE) handleInputEvent(binding, isActionDown, 0);
        }
    }

    public void handleInputEvent(Binding binding, boolean isActionDown) {
        handleInputEvent(binding, isActionDown, 0);
    }

    public void handleInputEvent(Binding binding, boolean isActionDown, float offset) {
        if (binding.isGamepad()) {
            WinHandler winHandler = xServer != null ? xServer.getWinHandler() : null;
            GamepadState state = profile.getGamepadState();

            int buttonIdx = binding.ordinal() - Binding.GAMEPAD_BUTTON_A.ordinal();
            if (buttonIdx <= 11) {
                state.setPressed(buttonIdx, isActionDown);
            }
            else if (binding == Binding.GAMEPAD_LEFT_THUMB_UP || binding == Binding.GAMEPAD_LEFT_THUMB_DOWN) {
                state.thumbLY = isActionDown ? offset : 0;
            }
            else if (binding == Binding.GAMEPAD_LEFT_THUMB_LEFT || binding == Binding.GAMEPAD_LEFT_THUMB_RIGHT) {
                state.thumbLX = isActionDown ? offset : 0;
            }
            else if (binding == Binding.GAMEPAD_RIGHT_THUMB_UP || binding == Binding.GAMEPAD_RIGHT_THUMB_DOWN) {
                state.thumbRY = isActionDown ? offset : 0;
            }
            else if (binding == Binding.GAMEPAD_RIGHT_THUMB_LEFT || binding == Binding.GAMEPAD_RIGHT_THUMB_RIGHT) {
                state.thumbRX = isActionDown ? offset : 0;
            }
            else if (binding == Binding.GAMEPAD_DPAD_UP || binding == Binding.GAMEPAD_DPAD_RIGHT ||
                     binding == Binding.GAMEPAD_DPAD_DOWN || binding == Binding.GAMEPAD_DPAD_LEFT) {
                state.dpad[binding.ordinal() - Binding.GAMEPAD_DPAD_UP.ordinal()] = isActionDown;
            }

            if (winHandler != null) winHandler.gamepadHandler.sendGamepadState(profile);
        }
        else {
            if (binding == Binding.MOUSE_MOVE_LEFT || binding == Binding.MOUSE_MOVE_RIGHT) {
                mouseMoveOffset.x = isActionDown ? (offset != 0 ? offset : (binding == Binding.MOUSE_MOVE_LEFT ? -1 : 1)) : 0;
                if (isActionDown) createMouseMoveTimer();
            }
            else if (binding == Binding.MOUSE_MOVE_DOWN || binding == Binding.MOUSE_MOVE_UP) {
                mouseMoveOffset.y = isActionDown ? (offset != 0 ? offset : (binding == Binding.MOUSE_MOVE_UP ? -1 : 1)) : 0;
                if (isActionDown) createMouseMoveTimer();
            }
            else {
                if (xServer == null) {
                    try {
                        com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(),
                            "InputControls inject SKIP xServerNull binding=" + binding);
                    } catch (Throwable ignored) {}
                    return;
                }
                Pointer.Button pointerButton = binding.getPointerButton();
                WinHandler wh = xServer.getWinHandler();
                if (isActionDown) {
                    if (pointerButton != null) {
                        xServer.injectPointerButtonPress(pointerButton);
                        if (wh != null && !xServer.isRelativeMouseMovement()) {
                            int flags = MouseEventFlags.getFlagFor(pointerButton, true);
                            if (pointerButton == Pointer.Button.BUTTON_SCROLL_UP) {
                                wh.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), 120);
                            } else if (pointerButton == Pointer.Button.BUTTON_SCROLL_DOWN) {
                                wh.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), -120);
                            } else {
                                wh.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), 0);
                            }
                        }
                        try {
                            com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(),
                                "InputControls inject POINTER press " + binding);
                        } catch (Throwable ignored) {}
                    } else {
                        xServer.injectKeyPress(binding.keycode);
                        try {
                            com.rpgrtl.shell.ShellLog.INSTANCE.info(getContext(),
                                "InputControls inject KEY press " + binding + " code=" + binding.keycode);
                        } catch (Throwable ignored) {}
                    }
                } else {
                    if (pointerButton != null) {
                        xServer.injectPointerButtonRelease(pointerButton);
                        if (wh != null && !xServer.isRelativeMouseMovement()) {
                            int flags = MouseEventFlags.getFlagFor(pointerButton, false);
                            wh.mouseEventAbsolute(flags, xServer.pointer.getX(), xServer.pointer.getY(), 0);
                        }
                    } else {
                        xServer.injectKeyRelease(binding.keycode);
                    }
                }
            }
        }
    }

    public Bitmap getIcon(byte id) {
        if (id < 0 || id >= icons.length) return null;
        if (icons[id] == null) {
            Context context = getContext();
            String[] paths = {
                "inputcontrols/icons/" + id + ".png",
                "winlator/inputcontrols/icons/" + id + ".png"
            };
            for (String path : paths) {
                try (InputStream is = context.getAssets().open(path)) {
                    icons[id] = BitmapFactory.decodeStream(is);
                    if (icons[id] != null) break;
                } catch (IOException ignored) {}
            }
        }
        return icons[id];
    }
}

