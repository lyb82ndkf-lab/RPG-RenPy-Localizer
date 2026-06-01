package com.rpgrtl.shell.wine

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import kotlin.math.roundToInt

class FloatingToolbar(
    context: Context,
    private val listener: Listener
) : LinearLayout(context) {
    interface Listener {
        fun onToolbarAction(action: String)
    }

    private var expanded = false
    private var touchBlocked = false

    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER
        render(false)
    }

    fun setTouchBlocked(blocked: Boolean) {
        touchBlocked = blocked
        if (expanded) render(true)
    }

    fun collapse() {
        if (expanded) render(false)
    }

    private fun render(showPanel: Boolean) {
        expanded = showPanel
        removeAllViews()
        addView(button(if (expanded) "<" else "T", if (expanded) "收起" else "工具") {
            render(!expanded)
        })
        if (!expanded) return

        addView(button("R", "实时") { fire("runtime") })
        addView(button("H", "汉化") { fire("translate") })
        addView(button("D", "数据") { fire("data") })
        addView(button("K", "键盘") { fire("keyboard") })
        addView(button(if (touchBlocked) "ON" else "OFF", if (touchBlocked) "恢复触摸" else "禁用触摸", touchBlocked) { fire("touch") })
        addView(button("ROT", "旋转") { fire("rotate") })
        addView(button("X", "关闭") { fire("close") })

        postDelayed({ collapse() }, AUTO_COLLAPSE_MS)
    }

    private fun fire(action: String) {
        listener.onToolbarAction(action)
        if (action != "touch") postDelayed({ collapse() }, 500)
    }

    private fun button(textValue: String, label: String, active: Boolean = false, action: () -> Unit): TextView {
        return TextView(context).apply {
            text = textValue
            contentDescription = label
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            textSize = if (textValue.length > 2) 10f else 14f
            background = GradientDrawable().apply {
                shape = GradientDrawable.RECTANGLE
                cornerRadii = floatArrayOf(10f.dp(), 0f, 0f, 0f, 0f, 0f, 10f.dp(), 0f)
                setColor(if (active) 0xCCB23A3A.toInt() else 0xAA000000.toInt())
                setStroke(1f.dp().roundToInt(), 0x55FFFFFF)
            }
            setOnClickListener { action() }
            layoutParams = LayoutParams(42f.dp().roundToInt(), 42f.dp().roundToInt()).apply {
                bottomMargin = 2f.dp().roundToInt()
            }
        }
    }

    private fun Float.dp(): Float = this * resources.displayMetrics.density

    companion object {
        private const val AUTO_COLLAPSE_MS = 10_000L
    }
}
