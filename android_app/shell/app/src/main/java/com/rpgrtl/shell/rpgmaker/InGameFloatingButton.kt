package com.rpgrtl.shell.rpgmaker

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.MotionEvent
import android.view.View
import android.widget.ImageView
import androidx.appcompat.widget.AppCompatImageView
import com.rpgrtl.shell.R
import kotlin.math.abs

class InGameFloatingButton(
    context: Context,
    private val onActivate: () -> Unit
) : AppCompatImageView(context) {
    private val edgeMargin = dp(14)
    private var downRawX = 0f
    private var downRawY = 0f
    private var startX = 0f
    private var startY = 0f
    private var dragged = false

    init {
        setImageResource(R.drawable.ic_rrl_logo)
        scaleType = ImageView.ScaleType.FIT_CENTER
        val pad = dp(4)
        setPadding(pad, pad, pad, pad)
        elevation = dp(8).toFloat()
        alpha = 0.90f
        background = GradientDrawable().apply {
            shape = GradientDrawable.OVAL
            setColor(Color.argb(240, 14, 18, 26))
            setStroke(dp(1.5f), Color.argb(180, 200, 207, 220))
        }
        contentDescription = "打开游戏工具 (RPGRenPyLocalizer)"
        setOnClickListener { onActivate() }
        setOnTouchListener(::handleTouch)
    }

    fun resetPosition() {
        post {
            val parentView = parent as? View ?: return@post
            x = (parentView.width - width - edgeMargin).coerceAtLeast(edgeMargin).toFloat()
            y = edgeMargin.toFloat()
        }
    }

    private fun handleTouch(view: View, event: MotionEvent): Boolean {
        val parentView = parent as? View ?: return false
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downRawX = event.rawX
                downRawY = event.rawY
                startX = x
                startY = y
                dragged = false
                view.parent.requestDisallowInterceptTouchEvent(true)
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = event.rawX - downRawX
                val dy = event.rawY - downRawY
                if (abs(dx) > dp(5) || abs(dy) > dp(5)) dragged = true
                x = (startX + dx).coerceIn(0f, (parentView.width - width).coerceAtLeast(0).toFloat())
                y = (startY + dy).coerceIn(0f, (parentView.height - height).coerceAtLeast(0).toFloat())
                return true
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                view.parent.requestDisallowInterceptTouchEvent(false)
                if (!dragged && event.actionMasked == MotionEvent.ACTION_UP) {
                    performClick()
                } else {
                    val left = edgeMargin.toFloat()
                    val right = (parentView.width - width - edgeMargin).coerceAtLeast(edgeMargin).toFloat()
                    animate().x(if (x + width / 2f < parentView.width / 2f) left else right).setDuration(160).start()
                }
                return true
            }
        }
        return false
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density + 0.5f).toInt()
    private fun dp(value: Float): Int = (value * resources.displayMetrics.density + 0.5f).toInt()
}

