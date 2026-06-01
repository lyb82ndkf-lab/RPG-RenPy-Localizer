package com.rpgrtl.engine.renderer.effects;

import com.rpgrtl.engine.renderer.material.ScreenMaterial;

public abstract class Effect {
    private ScreenMaterial material;

    protected ScreenMaterial createMaterial() {
        return null;
    }

    public ScreenMaterial getMaterial() {
        if (material == null) material = createMaterial();
        return material;
    }
}

