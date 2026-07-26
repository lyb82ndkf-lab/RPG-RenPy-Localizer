package com.rpgrtl.shell

import android.content.Context
import android.util.Log
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object ShellLog {
    private const val PREFS_NAME = "rpgrtl_runtime_log"
    private const val KEY_LOG = "runtime_log"
    private const val MAX_CHARS = 160_000
    @Volatile private var crashLoggerInstalled = false
    private val timestamp = ThreadLocal.withInitial {
        SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)
    }

    @Synchronized
    fun append(context: Context, level: String, message: String, error: Throwable? = null) {
        val appContext = context.applicationContext ?: context
        val line = buildString {
            append(timestamp.get()!!.format(Date()))
            append(" [")
            append(level)
            append("] ")
            append(message)
            if (error != null) {
                append('\n')
                append(Log.getStackTraceString(error))
            }
        }
        val prefs = appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val previous = prefs.getString(KEY_LOG, "").orEmpty()
        val next = (previous + line + "\n").takeLast(MAX_CHARS)
        prefs.edit().putString(KEY_LOG, next).commit()
    }

    fun info(context: Context, message: String) = append(context, "INFO", message)

    fun error(context: Context, message: String, error: Throwable? = null) =
        append(context, "ERROR", message, error)

    fun fatal(context: Context, message: String, error: Throwable? = null) =
        append(context, "FATAL", message, error)

    fun read(context: Context): String {
        val appContext = context.applicationContext ?: context
        return appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString(KEY_LOG, "")
            .orEmpty()
    }

    fun clear(context: Context) {
        val appContext = context.applicationContext ?: context
        appContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_LOG)
            .commit()
    }

    @Synchronized
    fun installCrashLogger(context: Context) {
        if (crashLoggerInstalled) return
        crashLoggerInstalled = true
        val appContext = context.applicationContext ?: context
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            try {
                fatal(appContext, "Uncaught exception on thread ${thread.name}", error)
            } catch (_: Throwable) {
            }
            previous?.uncaughtException(thread, error)
        }
    }
}
