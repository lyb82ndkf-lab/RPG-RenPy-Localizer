package com.rpgrtl.engine;

import android.content.Context;

/**
 * Tiny compatibility shim for Winlator settings references. The RPGTL UI owns
 * real settings; these defaults keep engine-side helpers compileable.
 */
public final class SettingsFragment {
    public static final int APP_THEME_LIGHT = 0;
    public static final int APP_THEME_DARK = 1;

    private SettingsFragment() {}

    public static void resetBox64Version(Context context) {
        context.getSharedPreferences("androidx.preference.PreferenceManager", Context.MODE_PRIVATE)
            .edit()
            .remove("current_box64_version")
            .apply();
    }
}
