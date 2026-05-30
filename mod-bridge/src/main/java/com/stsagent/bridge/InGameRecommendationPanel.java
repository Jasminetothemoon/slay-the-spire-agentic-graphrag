package com.stsagent.bridge;

import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.helpers.ImageMaster;

public class InGameRecommendationPanel {
    private static final long STALE_AFTER_MS = 15000L;
    private RecommendationResult latest;
    private String statusMessage = "";
    private long statusReceivedAt = 0L;
    private boolean visible = true;

    public void update(RecommendationResult result) {
        if (result != null && result.hasContent()) {
            latest = result;
            statusMessage = "";
        }
    }

    public void updateStatus(String message) {
        statusMessage = message == null ? "" : message;
        statusReceivedAt = System.currentTimeMillis();
    }

    public void toggleVisible() {
        visible = !visible;
    }

    public boolean isVisible() {
        return visible;
    }

    public void render(SpriteBatch sb) {
        if (!visible) {
            return;
        }

        long now = System.currentTimeMillis();
        boolean hasFreshRecommendation = latest != null && now - latest.receivedAt <= STALE_AFTER_MS;
        boolean hasFreshStatus = !statusMessage.isEmpty() && now - statusReceivedAt <= STALE_AFTER_MS;
        if (!hasFreshRecommendation && !hasFreshStatus) {
            return;
        }

        float scale = Settings.scale;
        float width = 440.0F * scale;
        float height = panelHeight(hasFreshRecommendation);
        float x = Settings.WIDTH - width - 24.0F * scale;
        float y = Settings.HEIGHT - height - 104.0F * scale;
        float padding = 14.0F * scale;

        Color previous = sb.getColor().cpy();
        sb.setColor(new Color(0.03F, 0.05F, 0.08F, 0.78F));
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y, width, height);
        sb.setColor(new Color(0.10F, 0.45F, 0.78F, 0.95F));
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y + height - 4.0F * scale, width, 4.0F * scale);
        sb.setColor(previous);

        float textX = x + padding;
        float textY = y + height - padding;
        FontHelper.renderFontLeftTopAligned(sb, FontHelper.topPanelInfoFont, "STS Agent", textX, textY, Settings.GOLD_COLOR);

        if (!hasFreshRecommendation) {
            FontHelper.renderSmartText(
                sb,
                FontHelper.tipBodyFont,
                clamp(statusMessage, 120),
                textX,
                textY - 30.0F * scale,
                width - padding * 2.0F,
                22.0F * scale,
                Settings.RED_TEXT_COLOR
            );
            return;
        }

        FontHelper.renderFontLeftTopAligned(
            sb,
            FontHelper.tipHeaderFont,
            latest.displayName(),
            textX,
            textY - 26.0F * scale,
            Settings.CREAM_COLOR
        );

        String metrics = "Score " + latest.score + " | Confidence " + latest.confidence;
        FontHelper.renderFontLeftTopAligned(
            sb,
            FontHelper.topPanelInfoFont,
            metrics,
            textX,
            textY - 54.0F * scale,
            Settings.GREEN_TEXT_COLOR
        );

        if (!latest.reason.isEmpty()) {
            FontHelper.renderSmartText(
                sb,
                FontHelper.tipBodyFont,
                clamp(latest.reason, 92),
                textX,
                textY - 78.0F * scale,
                width - padding * 2.0F,
                22.0F * scale,
                Settings.CREAM_COLOR
            );
        }

        if (!latest.risk.isEmpty()) {
            FontHelper.renderSmartText(
                sb,
                FontHelper.tipBodyFont,
                "Risk: " + clamp(latest.risk, 84),
                textX,
                textY - 104.0F * scale,
                width - padding * 2.0F,
                22.0F * scale,
                Settings.RED_TEXT_COLOR
            );
        }
    }

    private float panelHeight(boolean hasFreshRecommendation) {
        float scale = Settings.scale;
        if (!hasFreshRecommendation) {
            return 84.0F * scale;
        }
        return latest.risk.isEmpty() ? 118.0F * scale : 142.0F * scale;
    }

    private String clamp(String text, int maxLength) {
        if (text == null || text.length() <= maxLength) {
            return text == null ? "" : text;
        }
        return text.substring(0, maxLength - 3) + "...";
    }
}
