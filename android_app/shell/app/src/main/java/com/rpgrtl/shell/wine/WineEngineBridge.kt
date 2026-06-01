package com.rpgrtl.shell.wine

import android.app.Activity
import android.content.Intent
import android.net.Uri
import org.json.JSONObject

class WineEngineBridge(private val activity: Activity) {
    fun launch(
        gameUri: Uri?,
        title: String = "",
        containerId: Int = 0,
        box64Preset: String = "PERFORMANCE",
        graphicsDriver: String = "auto"
    ): JSONObject {
        if (gameUri == null) {
            return JSONObject()
                .put("ok", false)
                .put("error", "Please select a game folder first.")
        }
        val gamePath = gameUri.toString()

        val intent = Intent(activity, WineDisplayActivity::class.java).apply {
            putExtra(WineDisplayActivity.EXTRA_GAME_URI, gamePath)
            putExtra(WineDisplayActivity.EXTRA_GAME_TITLE, title)
            putExtra(WineDisplayActivity.EXTRA_CONTAINER_ID, containerId)
            putExtra(WineDisplayActivity.EXTRA_BOX64_PRESET, box64Preset)
            putExtra(WineDisplayActivity.EXTRA_GRAPHICS_DRIVER, graphicsDriver)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
        activity.startActivity(intent)

        return JSONObject()
            .put("ok", true)
            .put("backend", "wine")
            .put("box64Preset", box64Preset)
            .put("graphicsDriver", graphicsDriver)
            .put("gamePath", gamePath)
    }
}
