package com.rpgrtl.engine;

import android.app.Activity;
import android.content.Context;

/**
 * Compatibility stub for shortcut configuration dialogs. The RPGTL game
 * library replaces Winlator's shortcut screen.
 */
public class ShortcutsFragment {
    private final Activity activity;

    public ShortcutsFragment(Activity activity) {
        this.activity = activity;
    }

    public Activity getActivity() {
        return activity;
    }

    public Context getContext() {
        return activity;
    }

    public void loadShortcutsList() {}

    public void refreshContent() {}
}
