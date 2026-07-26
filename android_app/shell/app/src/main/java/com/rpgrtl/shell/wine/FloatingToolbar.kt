package com.rpgrtl.shell.wine

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import kotlin.math.roundToInt

/**
 * Compact side toolbar with line-art SVG-style icons and Chinese labels.
 * Replaces the old single-letter R/H/D/K/C strip.
 */
class FloatingToolbar(
    context: Context,
    private val listener: Listener
) : LinearLayout(context) {
    interface Listener {
        fun onToolbarAction(action: String)
    }

    private var expanded = false
    /** true = direct tap (point-and-click, hide cursor); false = pointer/trackpad mode */
    private var directTapMode = true
    private var editMode = false
    private var liveTranslationEnabled = true

    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER
        render(false)
    }

    fun setDirectTapMode(direct: Boolean) {
        directTapMode = direct
        if (expanded) render(true)
    }

    fun isDirectTapMode(): Boolean = directTapMode

    /** @deprecated use setDirectTapMode — kept for binary compatibility during refactor */
    fun setTouchBlocked(blocked: Boolean) {
        // Old "touch blocked" mapped poorly; map to pointer mode when blocked.
        setDirectTapMode(!blocked)
    }

    fun setEditMode(active: Boolean) {
        editMode = active
        if (expanded) render(true)
    }

    fun setLiveTranslationEnabled(enabled: Boolean) {
        liveTranslationEnabled = enabled
        if (expanded) render(true)
    }

    fun isLiveTranslationEnabled(): Boolean = liveTranslationEnabled

    fun collapse() {
        if (expanded) render(false)
    }

    private fun render(showPanel: Boolean) {
        expanded = showPanel
        removeAllViews()
        removeCallbacks(autoCollapse)

        addView(
            iconButton(
                icon = if (expanded) Icon.CHEVRON_RIGHT else Icon.MENU,
                label = if (expanded) "收起" else "菜单",
                active = expanded
            ) { render(!expanded) }
        )
        if (!expanded) return

        addView(
            iconButton(
                icon = Icon.TRANSLATE,
                label = if (liveTranslationEnabled) "实时汉化·开" else "实时汉化·关",
                active = liveTranslationEnabled
            ) { fire("live_translation") }
        )
        addView(iconButton(Icon.DATABASE, "日志") { fire("live_log") })
        addView(iconButton(Icon.DATABASE, "数据") { fire("data") })
        addView(iconButton(Icon.KEYBOARD, "键盘") { fire("keyboard") })
        addView(
            iconButton(
                icon = Icon.GAMEPAD,
                label = if (editMode) "完成编辑" else "键位",
                active = editMode
            ) { fire("controls") }
        )
        // Input mode toggle: 直接点 = hide cursor, tap where finger is
        //                  指针 = show cursor, swipe moves it, tap clicks at cursor
        addView(
            iconButton(
                icon = if (directTapMode) Icon.TOUCH else Icon.TOUCH_OFF,
                label = if (directTapMode) "直接点" else "指针",
                active = directTapMode
            ) { fire("touch") }
        )
        addView(iconButton(Icon.ROTATE, "旋转") { fire("rotate") })
        addView(iconButton(Icon.CLOSE, "退出", danger = true) { fire("close") })

        postDelayed(autoCollapse, AUTO_COLLAPSE_MS)
    }

    private val autoCollapse = Runnable { collapse() }

    private fun fire(action: String) {
        removeCallbacks(autoCollapse)
        listener.onToolbarAction(action)
        if (action != "touch" && action != "controls" && action != "live_translation" && action != "live_log") {
            postDelayed({ collapse() }, 400)
        } else {
            // Keep panel open after mode toggle so user sees the new label.
            if (expanded) render(true)
            postDelayed(autoCollapse, AUTO_COLLAPSE_MS)
        }
    }

    private fun iconButton(
        icon: Icon,
        label: String,
        active: Boolean = false,
        danger: Boolean = false,
        action: () -> Unit
    ): LinearLayout {
        val density = resources.displayMetrics.density
        val size = (46f * density).roundToInt()
        val iconSize = (22f * density).roundToInt()

        return LinearLayout(context).apply {
            orientation = VERTICAL
            gravity = Gravity.CENTER
            contentDescription = label
            isClickable = true
            isFocusable = true
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadii = floatArrayOf(
                    12f * density, 12f * density,
                    0f, 0f,
                    0f, 0f,
                    12f * density, 12f * density
                )
                setColor(
                    when {
                        danger -> 0xCC8B1E1E.toInt()
                        active -> 0xCC1E6BB8.toInt()
                        else -> 0xBB12141A.toInt()
                    }
                )
                setStroke((1f * density).roundToInt(), 0x55FFFFFF)
            }
            setPadding(0, (4f * density).roundToInt(), 0, (4f * density).roundToInt())
            layoutParams = LayoutParams(size, LayoutParams.WRAP_CONTENT).apply {
                bottomMargin = (3f * density).roundToInt()
            }
            minimumHeight = size

            addView(LineIconView(context, icon).apply {
                layoutParams = LayoutParams(iconSize, iconSize).apply {
                    gravity = Gravity.CENTER_HORIZONTAL
                }
            })
            addView(TextView(context).apply {
                text = label
                gravity = Gravity.CENTER
                setTextColor(0xEEFFFFFF.toInt())
                textSize = 9f
                setSingleLine()
                layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
            })
            setOnClickListener { action() }
        }
    }

    private enum class Icon {
        MENU, CHEVRON_RIGHT, PLAY, TRANSLATE, DATABASE, KEYBOARD,
        GAMEPAD, TOUCH, TOUCH_OFF, ROTATE, CLOSE
    }

    /** Lightweight vector line icons drawn with Canvas (no bitmap assets). */
    private class LineIconView(context: Context, private val icon: Icon) : View(context) {
        private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            strokeCap = Paint.Cap.ROUND
            strokeJoin = Paint.Join.ROUND
            color = Color.WHITE
            strokeWidth = 2.2f * resources.displayMetrics.density
        }
        private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.FILL
            color = Color.WHITE
        }
        private val path = Path()
        private val rect = RectF()

        override fun onDraw(canvas: Canvas) {
            val w = width.toFloat()
            val h = height.toFloat()
            val p = w * 0.18f
            val s = stroke.strokeWidth
            stroke.strokeWidth = (w * 0.09f).coerceAtLeast(s * 0.7f)

            when (icon) {
                Icon.MENU -> {
                    // hamburger
                    val y1 = h * 0.32f
                    val y2 = h * 0.5f
                    val y3 = h * 0.68f
                    canvas.drawLine(p, y1, w - p, y1, stroke)
                    canvas.drawLine(p, y2, w - p, y2, stroke)
                    canvas.drawLine(p, y3, w - p, y3, stroke)
                }
                Icon.CHEVRON_RIGHT -> {
                    path.reset()
                    path.moveTo(w * 0.38f, p)
                    path.lineTo(w * 0.62f, h * 0.5f)
                    path.lineTo(w * 0.38f, h - p)
                    canvas.drawPath(path, stroke)
                }
                Icon.PLAY -> {
                    path.reset()
                    path.moveTo(w * 0.34f, p)
                    path.lineTo(w * 0.78f, h * 0.5f)
                    path.lineTo(w * 0.34f, h - p)
                    path.close()
                    canvas.drawPath(path, stroke)
                }
                Icon.TRANSLATE -> {
                    // globe-ish ring + A
                    rect.set(p, p, w - p, h - p)
                    canvas.drawOval(rect, stroke)
                    canvas.drawLine(w * 0.5f, p, w * 0.5f, h - p, stroke)
                    canvas.drawLine(p, h * 0.5f, w - p, h * 0.5f, stroke)
                }
                Icon.DATABASE -> {
                    rect.set(p, p * 0.9f, w - p, h * 0.38f)
                    canvas.drawOval(rect, stroke)
                    canvas.drawLine(p, h * 0.28f, p, h * 0.72f, stroke)
                    canvas.drawLine(w - p, h * 0.28f, w - p, h * 0.72f, stroke)
                    rect.set(p, h * 0.55f, w - p, h - p * 0.9f)
                    canvas.drawOval(rect, stroke)
                }
                Icon.KEYBOARD -> {
                    rect.set(p, h * 0.28f, w - p, h * 0.72f)
                    canvas.drawRoundRect(rect, w * 0.08f, w * 0.08f, stroke)
                    val key = w * 0.1f
                    val gap = w * 0.06f
                    var x = p + gap
                    val y = h * 0.42f
                    repeat(3) {
                        canvas.drawRect(x, y, x + key, y + key, stroke)
                        x += key + gap
                    }
                }
                Icon.GAMEPAD -> {
                    rect.set(p, h * 0.3f, w - p, h * 0.7f)
                    canvas.drawRoundRect(rect, w * 0.2f, w * 0.2f, stroke)
                    canvas.drawCircle(w * 0.35f, h * 0.5f, w * 0.07f, fill)
                    canvas.drawCircle(w * 0.65f, h * 0.42f, w * 0.05f, fill)
                    canvas.drawCircle(w * 0.72f, h * 0.55f, w * 0.05f, fill)
                }
                Icon.TOUCH -> {
                    // finger tip circle + stem
                    canvas.drawCircle(w * 0.5f, h * 0.38f, w * 0.16f, stroke)
                    path.reset()
                    path.moveTo(w * 0.5f, h * 0.54f)
                    path.quadTo(w * 0.5f, h * 0.78f, w * 0.62f, h - p)
                    canvas.drawPath(path, stroke)
                }
                Icon.TOUCH_OFF -> {
                    canvas.drawCircle(w * 0.5f, h * 0.38f, w * 0.16f, stroke)
                    path.reset()
                    path.moveTo(w * 0.5f, h * 0.54f)
                    path.quadTo(w * 0.5f, h * 0.78f, w * 0.62f, h - p)
                    canvas.drawPath(path, stroke)
                    canvas.drawLine(p, p, w - p, h - p, stroke)
                }
                Icon.ROTATE -> {
                    rect.set(p, p, w - p, h - p)
                    canvas.drawArc(rect, 40f, 260f, false, stroke)
                    path.reset()
                    path.moveTo(w * 0.72f, p * 1.1f)
                    path.lineTo(w - p, h * 0.28f)
                    path.lineTo(w * 0.58f, h * 0.3f)
                    canvas.drawPath(path, stroke)
                }
                Icon.CLOSE -> {
                    canvas.drawLine(p, p, w - p, h - p, stroke)
                    canvas.drawLine(w - p, p, p, h - p, stroke)
                }
            }
        }
    }

    companion object {
        private const val AUTO_COLLAPSE_MS = 12_000L
    }
}
