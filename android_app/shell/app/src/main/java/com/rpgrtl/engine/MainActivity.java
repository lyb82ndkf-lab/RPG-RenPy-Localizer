package com.rpgrtl.engine;

/**
 * Compatibility constants expected by transplanted Winlator runtime helpers.
 * RPGTL keeps its real launcher at com.rpgrtl.shell.MainActivity.
 */
public abstract class MainActivity extends XServerDisplayActivity {
    public static final boolean DEBUG_MODE = false;
    public static final int OPEN_FILE_REQUEST_CODE = 4010;
    public static final int CONTAINER_PATTERN_COMPRESSION_LEVEL = 10;
}
