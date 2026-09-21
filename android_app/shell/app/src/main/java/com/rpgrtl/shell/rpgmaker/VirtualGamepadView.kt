package com.rpgrtl.shell.rpgmaker

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.webkit.WebView
import android.widget.FrameLayout
import androidx.appcompat.widget.AppCompatTextView
import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.sqrt

class VirtualGamepadView(
    context: Context,
    private val webView: WebView
) : FrameLayout(context) {
    private companion object {
        const val DARK_BUTTON_COLOR = "#18232D"
        const val DARK_JOYSTICK_COLOR = "#151F28"
        const val DARK_FOREGROUND_COLOR = "#E7EDF2"
    }

    private data class Control(
        val id: String,
        val label: String,
        val keyCode: Int,
        val code: String,
        val x: Float,
        val y: Float,
        val scale: Float,
        val opacity: Float,
        val background: Int,
        val foreground: Int,
        val type: String,
        val joystickMode: String,
        val joystickStyle: String,
        val bindingType: String
    )

    private val controls = mutableListOf<Control>()
    private var controlsAlpha = 0.58f
    private var vibrationMs = 18
    private var currentProfileJson = ""
    private var safeInsetLeft = 0
    private var safeInsetTop = 0
    private var safeInsetRight = 0
    private var safeInsetBottom = 0

    init {
        isClickable = false
        isFocusable = false
        clipChildren = false
        applyProfile("")
    }

    fun setGamepadVisible(visible: Boolean) {
        visibility = if (visible) View.VISIBLE else View.GONE
    }

    fun setControlsAlpha(value: Float) {
        controlsAlpha = value.coerceIn(0.1f, 1f)
        children().forEach { it.alpha = controlsAlpha }
    }

    fun resetLayout() = applyProfile("")

    fun setSafeInsets(left: Int, top: Int, right: Int, bottom: Int) {
        safeInsetLeft = left.coerceAtLeast(0)
        safeInsetTop = top.coerceAtLeast(0)
        safeInsetRight = right.coerceAtLeast(0)
        safeInsetBottom = bottom.coerceAtLeast(0)
        post { positionControls(width, height) }
    }

    fun applyProfile(json: String) {
        val profile = runCatching { JSONObject(json) }.getOrNull() ?: defaultProfile()
        controlsAlpha = profile.optDouble("opacity", 0.58).toFloat().coerceIn(0.1f, 1f)
        vibrationMs = profile.optInt("vibrationMs", 18).coerceIn(0, 250)
        controls.clear()
        var items = profile.optJSONArray("controls") ?: JSONArray()
        var hasJoystick = false
        val legacyDirections = mutableSetOf<String>()
        for (i in 0 until items.length()) {
            val candidate = items.optJSONObject(i) ?: continue
            if (candidate.optString("type") == "joystick") hasJoystick = true
            if (candidate.optString("id") in setOf("up", "down", "left", "right")) legacyDirections += candidate.optString("id")
        }
        if (!hasJoystick && legacyDirections.size == 4) {
            val migrated = JSONArray().put(joystick("move", .16, .78, "arrows", "dpad"))
            for (i in 0 until items.length()) {
                val candidate = items.optJSONObject(i) ?: continue
                if (candidate.optString("id") !in legacyDirections) migrated.put(candidate)
            }
            items = migrated
            profile.put("controls", items)
        }
        for (i in 0 until items.length()) {
            val item = items.optJSONObject(i) ?: continue
            controls += Control(
                id = item.optString("id", "button$i"),
                label = item.optString("label", item.optString("code", "?")),
                keyCode = item.optInt("keyCode", 0),
                code = item.optString("code", ""),
                x = item.optDouble("x", 0.5).toFloat().coerceIn(0.02f, 0.98f),
                y = item.optDouble("y", 0.5).toFloat().coerceIn(0.04f, 0.96f),
                scale = item.optDouble("scale", 1.0).toFloat().coerceIn(0.5f, 2.5f),
                opacity = item.optDouble("opacity", controlsAlpha.toDouble()).toFloat().coerceIn(0.1f, 1f),
                background = parseColor(if (item.optString("type", "button") == "joystick") DARK_JOYSTICK_COLOR else DARK_BUTTON_COLOR, Color.rgb(24, 35, 45)),
                foreground = parseColor(DARK_FOREGROUND_COLOR, Color.WHITE),
                type = item.optString("type", "button"),
                joystickMode = item.optString("joystickMode", "arrows"),
                joystickStyle = item.optString("joystickStyle", "stick"),
                bindingType = item.optString("bindingType", "keyboard")
            )
        }
        if (controls.isEmpty()) {
            val fallback = defaultProfile().optJSONArray("controls") ?: JSONArray()
            applyProfile(JSONObject().put("opacity", controlsAlpha).put("vibrationMs", vibrationMs).put("controls", fallback).toString())
            return
        }
        currentProfileJson = profile.toString()
        rebuildControls()
    }

    fun exportProfile(): String = currentProfileJson.ifBlank { defaultProfile().toString() }

    fun releaseAllKeys() {
        controls.forEach {
            if (it.type == "joystick") releaseJoystickDirections(it.joystickMode)
            else dispatchControlEvent(false, it)
        }
    }

    fun vibrate(durationMs: Int = vibrationMs, strength: Int = VibrationEffect.DEFAULT_AMPLITUDE) {
        val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator ?: return
        if (!vibrator.hasVibrator() || durationMs <= 0) return
        @Suppress("DEPRECATION")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(durationMs.toLong(), strength.coerceIn(1, 255)))
        } else {
            vibrator.vibrate(durationMs.toLong())
        }
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        positionControls(w, h)
    }

    private fun rebuildControls() {
        removeAllViews()
        controls.forEach { control ->
            if (control.type == "joystick") {
                val size = dp((116 * control.scale).toInt())
                val joystick = JoystickView(context, control).apply {
                    alpha = control.opacity
                    tag = control.id
                    isClickable = true
                    isFocusable = false
                }
                addView(joystick, LayoutParams(size, size))
            } else {
                val size = dp((58 * control.scale).toInt())
                val button = AppCompatTextView(context).apply {
                    text = control.label
                    textSize = if (control.label.length <= 1) 24f else 12f
                    gravity = Gravity.CENTER
                    setTextColor(control.foreground)
                    isClickable = true
                    isFocusable = false
                    elevation = dp(4).toFloat()
                    alpha = control.opacity
                    tag = control.id
                    background = GradientDrawable().apply {
                        shape = GradientDrawable.OVAL
                        setColor(control.background)
                        setStroke(dp(1), Color.argb(210, 255, 255, 255))
                    }
                    setOnTouchListener { view, event ->
                        when (event.actionMasked) {
                            MotionEvent.ACTION_DOWN -> {
                                view.isPressed = true
                                vibrate()
                                dispatchControlEvent(true, control)
                                true
                            }
                            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                                view.isPressed = false
                                dispatchControlEvent(false, control)
                                true
                            }
                            else -> true
                        }
                    }
                }
                addView(button, LayoutParams(size, size))
            }
        }
        post { positionControls(width, height) }
    }

    private inner class JoystickView(context: Context, private val control: Control) : View(context) {
        private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = control.background; style = Paint.Style.FILL }
        private val linePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(215, Color.red(control.foreground), Color.green(control.foreground), Color.blue(control.foreground))
            style = Paint.Style.STROKE
            strokeWidth = dp(2).toFloat()
        }
        private val knobPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.argb(225, Color.red(control.foreground), Color.green(control.foreground), Color.blue(control.foreground))
            style = Paint.Style.FILL
        }
        private var knobX = 0f
        private var knobY = 0f
        private var held = emptySet<String>()

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            val cx = width / 2f
            val cy = height / 2f
            val radius = width.coerceAtMost(height) * .46f
            canvas.drawCircle(cx, cy, radius, ringPaint)
            canvas.drawCircle(cx, cy, radius, linePaint)
            if (control.joystickStyle == "dpad") {
                val arm = radius * .72f
                linePaint.strokeWidth = radius * .28f
                canvas.drawLine(cx - arm, cy, cx + arm, cy, linePaint)
                canvas.drawLine(cx, cy - arm, cx, cy + arm, linePaint)
                linePaint.strokeWidth = dp(2).toFloat()
            }
            canvas.drawCircle(cx + knobX, cy + knobY, radius * .31f, knobPaint)
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                    if (event.actionMasked == MotionEvent.ACTION_DOWN) vibrate()
                    val cx = width / 2f
                    val cy = height / 2f
                    var dx = event.x - cx
                    var dy = event.y - cy
                    val radius = width.coerceAtMost(height) * .32f
                    val distance = sqrt(dx * dx + dy * dy)
                    if (distance > radius && distance > 0f) {
                        dx = dx / distance * radius
                        dy = dy / distance * radius
                    }
                    knobX = dx
                    knobY = dy
                    updateDirections(dx, dy, radius)
                    invalidate()
                    return true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    setHeld(emptySet())
                    knobX = 0f
                    knobY = 0f
                    invalidate()
                    return true
                }
            }
            return true
        }

        private fun updateDirections(dx: Float, dy: Float, radius: Float) {
            val dead = radius * .26f
            val next = linkedSetOf<String>()
            if (abs(dx) > dead) next += if (dx < 0) "left" else "right"
            if (abs(dy) > dead) next += if (dy < 0) "up" else "down"
            setHeld(next)
        }

        private fun setHeld(next: Set<String>) {
            (held - next).forEach { dispatchJoystickDirection(false, it, control.joystickMode) }
            (next - held).forEach { dispatchJoystickDirection(true, it, control.joystickMode) }
            held = next
        }
    }

    private fun positionControls(w: Int, h: Int) {
        if (w <= 0 || h <= 0) return
        val usableWidth = (w - safeInsetLeft - safeInsetRight).coerceAtLeast(1)
        val usableHeight = (h - safeInsetTop - safeInsetBottom).coerceAtLeast(1)
        controls.forEachIndexed { index, control ->
            val view = getChildAt(index) ?: return@forEachIndexed
            val minX = safeInsetLeft.toFloat()
            val maxX = (w - safeInsetRight - view.layoutParams.width).coerceAtLeast(safeInsetLeft).toFloat()
            val minY = safeInsetTop.toFloat()
            val maxY = (h - safeInsetBottom - view.layoutParams.height).coerceAtLeast(safeInsetTop).toFloat()
            view.x = (safeInsetLeft + usableWidth * control.x - view.layoutParams.width / 2f).coerceIn(minX, maxX)
            view.y = (safeInsetTop + usableHeight * control.y - view.layoutParams.height / 2f).coerceIn(minY, maxY)
        }
    }

    private fun dispatchControlEvent(down: Boolean, control: Control) {
        if (control.bindingType == "mouse" || control.code.startsWith("Mouse")) dispatchMouseEvent(down, control.keyCode)
        else dispatchKeyboardEvent(down, control.keyCode, control.code)
    }

    private fun dispatchJoystickDirection(down: Boolean, direction: String, mode: String) {
        val wasd = mode == "wasd"
        val binding = when (direction) {
            "up" -> if (wasd) 87 to "KeyW" else 38 to "ArrowUp"
            "down" -> if (wasd) 83 to "KeyS" else 40 to "ArrowDown"
            "left" -> if (wasd) 65 to "KeyA" else 37 to "ArrowLeft"
            else -> if (wasd) 68 to "KeyD" else 39 to "ArrowRight"
        }
        dispatchKeyboardEvent(down, binding.first, binding.second)
    }

    private fun releaseJoystickDirections(mode: String) {
        listOf("up", "down", "left", "right").forEach { dispatchJoystickDirection(false, it, mode) }
    }

    private fun dispatchMouseEvent(down: Boolean, buttonCode: Int) {
        val eventType = if (down) "mousedown" else "mouseup"
        val button = when (buttonCode) { 2 -> 1; 3 -> 2; else -> 0 }
        val buttons = if (!down) 0 else when (button) { 1 -> 4; 2 -> 2; else -> 1 }
        val script = """
            (function(){
              var target = document.elementFromPoint(window.innerWidth / 2, window.innerHeight / 2) || document;
              var event = new MouseEvent('$eventType', {bubbles:true, cancelable:true, button:$button, buttons:$buttons, clientX:window.innerWidth/2, clientY:window.innerHeight/2});
              target.dispatchEvent(event);
            })();
        """.trimIndent()
        webView.evaluateJavascript(script, null)
    }

    private fun dispatchKeyboardEvent(down: Boolean, keyCode: Int, code: String) {
        if (keyCode <= 0) return
        val eventType = if (down) "keydown" else "keyup"
        val key = when (keyCode) {
            37 -> "ArrowLeft"; 38 -> "ArrowUp"; 39 -> "ArrowRight"; 40 -> "ArrowDown"
            13 -> "Enter"; 16 -> "Shift"; 17 -> "Control"; 18 -> "Alt"; 27 -> "Escape"; 32 -> " "
            in 65..90 -> keyCode.toChar().lowercaseChar().toString()
            else -> ""
        }
        val script = """
            (function(){
              var e;
              try {
                e = new KeyboardEvent('$eventType', {key:'$key', code:'${code.replace("'", "")}', bubbles:true, cancelable:true});
                try { Object.defineProperty(e, 'keyCode', {get:function(){return $keyCode;}}); } catch (_) {}
                try { Object.defineProperty(e, 'which', {get:function(){return $keyCode;}}); } catch (_) {}
              } catch (_) {
                e = document.createEvent('Event'); e.initEvent('$eventType', true, true);
                e.keyCode = $keyCode; e.which = $keyCode;
              }
              document.dispatchEvent(e);
            })();
        """.trimIndent()
        webView.evaluateJavascript(script, null)
    }

    private fun defaultProfile(): JSONObject = JSONObject().apply {
        put("opacity", 0.62)
        put("vibrationMs", 18)
        put("controls", JSONArray().apply {
            put(joystick("move", .16, .78, "arrows", "dpad"))
            put(control("ok", "A", 90, "KeyZ", .87, .72, 1.12))
            put(control("cancel", "B", 88, "KeyX", .76, .84, 1.0))
            put(control("menu", "Y", 27, "Escape", .76, .62, .92))
            put(control("dash", "X", 16, "ShiftLeft", .91, .88, .92))
        })
    }

    private fun joystick(id: String, x: Double, y: Double, mode: String, style: String) =
        JSONObject().put("id", id).put("type", "joystick").put("label", "摇杆")
            .put("joystickMode", mode).put("joystickStyle", style).put("x", x).put("y", y)
            .put("scale", 1.12).put("opacity", .58).put("bg", DARK_JOYSTICK_COLOR).put("fg", DARK_FOREGROUND_COLOR)

    private fun control(id: String, label: String, keyCode: Int, code: String, x: Double, y: Double, scale: Double = 1.0) =
        JSONObject().put("id", id).put("type", "button").put("label", label).put("keyCode", keyCode).put("code", code)
            .put("bindingType", "keyboard").put("x", x).put("y", y).put("scale", scale).put("opacity", .58)
            .put("bg", DARK_BUTTON_COLOR).put("fg", DARK_FOREGROUND_COLOR)

    private fun parseColor(value: String, fallback: Int): Int = runCatching { Color.parseColor(value) }.getOrDefault(fallback)
    private fun children(): Sequence<View> = sequence { for (i in 0 until childCount) yield(getChildAt(i)) }
    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()
}

