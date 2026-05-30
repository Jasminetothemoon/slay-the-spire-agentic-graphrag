package com.stsagent.bridge;

import basemod.BaseMod;
import basemod.interfaces.PostInitializeSubscriber;
import basemod.interfaces.PostRenderSubscriber;
import basemod.interfaces.PostUpdateSubscriber;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.Input;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;

@SpireInitializer
public class StsAgentBridgeMod implements PostInitializeSubscriber, PostUpdateSubscriber, PostRenderSubscriber {
    private static final long POLL_INTERVAL_MS = 800L;

    private final BridgeClient client;
    private final GameStateCollector collector;
    private final InGameRecommendationPanel panel;
    private long lastPostAt = 0L;
    private String lastSignature = "";

    public StsAgentBridgeMod() {
        BridgeConfig config = BridgeConfig.fromRuntime();
        this.client = new BridgeClient(config);
        this.collector = new GameStateCollector(config);
        this.panel = new InGameRecommendationPanel();
    }

    public static void initialize() {
        BaseMod.subscribe(new StsAgentBridgeMod());
    }

    @Override
    public void receivePostInitialize() {
        try {
            client.postState(collector.collectHeartbeatState());
        } catch (Exception ex) {
            System.out.println("[STS Agent Bridge] Ignoring post-initialize error: " + ex.getMessage());
        }
    }

    @Override
    public void receivePostUpdate() {
        try {
            if (Gdx.input != null && Gdx.input.isKeyJustPressed(Input.Keys.F8)) {
                panel.toggleVisible();
                System.out.println("[STS Agent Bridge] In-game panel visible: " + panel.isVisible());
            }

            if (AbstractDungeon.player == null) {
                return;
            }

            long now = System.currentTimeMillis();
            if (now - lastPostAt < POLL_INTERVAL_MS) {
                return;
            }

            BridgePayload payload = collector.collect();
            String signature = payload.signature();
            if (signature.equals(lastSignature)) {
                return;
            }

            lastPostAt = now;
            lastSignature = signature;

            if (payload.hasDecision()) {
                RecommendationResult result = client.postRecommendation(payload);
                if (result != null && result.hasContent()) {
                    panel.update(result);
                } else if (client.hasLastError()) {
                    panel.updateStatus(client.lastError());
                } else {
                    panel.updateStatus("No recommendation found in API response.");
                }
            } else {
                client.postState(payload.stateJson());
                if (client.hasLastError()) {
                    panel.updateStatus(client.lastError());
                }
            }
        } catch (Exception ex) {
            panel.updateStatus("Mod bridge update failed: " + ex.getMessage());
            System.out.println("[STS Agent Bridge] Ignoring update error: " + ex.getMessage());
        }
    }

    @Override
    public void receivePostRender(SpriteBatch sb) {
        try {
            panel.render(sb);
        } catch (Exception ex) {
            System.out.println("[STS Agent Bridge] Ignoring render error: " + ex.getMessage());
        }
    }
}
