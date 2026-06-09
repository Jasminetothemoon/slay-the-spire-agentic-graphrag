package com.stsagent.bridge;

import com.badlogic.gdx.graphics.Color;
import com.badlogic.gdx.graphics.g2d.BitmapFont;
import com.badlogic.gdx.graphics.g2d.GlyphLayout;
import com.badlogic.gdx.graphics.g2d.SpriteBatch;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.FontHelper;
import com.megacrit.cardcrawl.helpers.ImageMaster;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import com.megacrit.cardcrawl.potions.AbstractPotion;
import com.megacrit.cardcrawl.relics.AbstractRelic;
import com.megacrit.cardcrawl.rewards.RewardItem;
import com.megacrit.cardcrawl.shop.ShopScreen;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class InGameRecommendationPanel {
    private static final long STATUS_STALE_AFTER_MS = 15000L;
    private RecommendationResult latest;
    private String statusMessage = "";
    private long statusReceivedAt = 0L;
    private String bridgeDebug = "";
    private boolean visible = true;
    private boolean debugVisible = false;
    private boolean chineseVisible = false;
    private int lastBadgeMatches = 0;
    private int lastBadgeUnmatched = 0;
    private String lastBadgeUnmatchedLabels = "";
    private RecommendationResult.OptionScore hoveredOption;
    private String preferredArchetype = "";

    public void update(RecommendationResult result) {
        if (result != null && result.hasContent()) {
            latest = result;
            statusMessage = "";
            bridgeDebug = result.debugSummary + " scores=" + result.optionScoreCount();
        }
    }

    public void updateStatus(String message) {
        latest = null;
        statusMessage = message == null ? "" : message;
        statusReceivedAt = System.currentTimeMillis();
    }

    public void updateDebug(String message) {
        bridgeDebug = message == null ? "" : message;
    }

    public void clear() {
        latest = null;
        statusMessage = "";
        statusReceivedAt = 0L;
    }

    public void toggleVisible() {
        visible = !visible;
    }

    public boolean isVisible() {
        return visible;
    }

    public void toggleDebugVisible() {
        debugVisible = !debugVisible;
    }

    public boolean isDebugVisible() {
        return debugVisible;
    }

    public void toggleLanguage() {
        chineseVisible = !chineseVisible;
    }

    public boolean isChineseVisible() {
        return chineseVisible;
    }

    public void updatePreferredArchetype(String archetypeId) {
        preferredArchetype = archetypeId == null ? "" : archetypeId;
    }

    public void render(SpriteBatch sb) {
        if (!visible) {
            return;
        }

        long now = System.currentTimeMillis();
        boolean hasFreshRecommendation = latest != null;
        boolean hasFreshStatus = !statusMessage.isEmpty() && now - statusReceivedAt <= STATUS_STALE_AFTER_MS;
        if (!hasFreshRecommendation && !hasFreshStatus) {
            return;
        }
        if (hasFreshRecommendation) {
            renderCandidateBadges(sb, latest);
        }

        float scale = Settings.scale;
        float width = 500.0F * scale;
        float height = panelHeight(hasFreshRecommendation);
        float x = Settings.WIDTH - width - 24.0F * scale;
        float y = Settings.HEIGHT - height - 104.0F * scale;
        float padding = 14.0F * scale;
        float contentWidth = width - padding * 2.0F;

        Color previous = sb.getColor().cpy();
        sb.setColor(new Color(0.03F, 0.05F, 0.08F, 0.78F));
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y, width, height);
        sb.setColor(new Color(0.10F, 0.45F, 0.78F, 0.95F));
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y + height - 4.0F * scale, width, 4.0F * scale);
        sb.setColor(previous);

        float textX = x + padding;
        float textY = y + height - padding;
        FontHelper.renderFontLeftTopAligned(sb, FontHelper.topPanelInfoFont, panelTitle(), textX, textY, Settings.GOLD_COLOR);

        if (!hasFreshRecommendation) {
            renderWrappedLines(
                sb,
                clamp(statusMessage, 120),
                textX,
                textY - 30.0F * scale,
                contentWidth,
                2,
                22.0F * scale,
                Settings.RED_TEXT_COLOR
            );
            return;
        }

        String sceneLabel = latest.sceneType.isEmpty() ? "Decision" : sceneDisplayName(latest.sceneType);
        FontHelper.renderFontLeftTopAligned(
            sb,
            FontHelper.topPanelInfoFont,
            sceneLabel + " | " + badgeText(),
            textX,
            textY - 24.0F * scale,
            Settings.GREEN_TEXT_COLOR
        );

        float cursorY = textY - 48.0F * scale;
        cursorY = renderWrappedLines(
            sb,
            clamp(latest.displayName(chineseVisible), chineseVisible ? 40 : 72),
            textX,
            cursorY,
            contentWidth,
            2,
            22.0F * scale,
            Settings.CREAM_COLOR,
            true
        );

        String metrics = metricsText();
        FontHelper.renderFontLeftTopAligned(
            sb,
            FontHelper.topPanelInfoFont,
            metrics,
            textX,
            cursorY - 2.0F * scale,
            Settings.GREEN_TEXT_COLOR
        );
        cursorY -= 24.0F * scale;

        String targetText = targetText();
        if (!targetText.isEmpty()) {
            FontHelper.renderFontLeftTopAligned(
                sb,
                FontHelper.topPanelInfoFont,
                targetText,
                textX,
                cursorY,
                Settings.BLUE_TEXT_COLOR
            );
            cursorY -= 22.0F * scale;
        }

        String reasonText = latest.reason(chineseVisible);
        if (!reasonText.isEmpty()) {
            cursorY = renderWrappedLines(
                sb,
                clamp(reasonText, chineseVisible ? 110 : 190),
                textX,
                cursorY,
                contentWidth,
                3,
                20.0F * scale,
                Settings.CREAM_COLOR
            );
        }

        String riskText = latest.risk(chineseVisible);
        if (!riskText.isEmpty()) {
            cursorY = renderWrappedLines(
                sb,
                riskLabel() + clamp(riskText, chineseVisible ? 54 : 96),
                textX,
                cursorY - 4.0F * scale,
                contentWidth,
                2,
                20.0F * scale,
                Settings.RED_TEXT_COLOR
            );
        }

        if (debugVisible) {
            String debug = bridgeDebug.isEmpty() ? "F9 Debug: waiting for bridge event." : bridgeDebug;
            debug = debug + " badges=" + lastBadgeMatches + "/" + latest.optionScoreCount() + " unmatched=" + lastBadgeUnmatched;
            if (!latest.optionScores.isEmpty() && !latest.optionScores.get(0).shopDebug().isEmpty()) {
                debug = debug + " topShop=" + latest.optionScores.get(0).shopDebug();
            }
            if (!lastBadgeUnmatchedLabels.isEmpty()) {
                debug = debug + " miss=" + lastBadgeUnmatchedLabels;
            }
            cursorY = renderWrappedLines(
                sb,
                "F9 Debug: " + clamp(debug, 220),
                textX,
                cursorY - 4.0F * scale,
                contentWidth,
                2,
                18.0F * scale,
                Settings.BLUE_TEXT_COLOR
            );
            if (!latest.whyNot.isEmpty()) {
                renderWrappedLines(
                    sb,
                    "Why: " + clamp(latest.whyNot, 130),
                    textX,
                    cursorY - 2.0F * scale,
                    contentWidth,
                    2,
                    18.0F * scale,
                    Settings.CREAM_COLOR
                );
            }
        }
        renderHoveredOptionDetail(sb);
    }

    private void renderCandidateBadges(SpriteBatch sb, RecommendationResult result) {
        lastBadgeMatches = 0;
        lastBadgeUnmatched = 0;
        lastBadgeUnmatchedLabels = "";
        hoveredOption = null;
        if (result == null || result.optionScores.isEmpty()) {
            return;
        }
        Set<RecommendationResult.OptionScore> matched = new HashSet<RecommendationResult.OptionScore>();
        String scene = result.sceneType;
        if ("card_reward".equals(scene)) {
            renderCardRewardBadges(sb, result, matched);
        } else if ("shop".equals(scene)) {
            renderShopBadges(sb, result, matched);
        } else if ("relic_reward".equals(scene)) {
            renderCombatRewardRelicBadges(sb, result, matched);
        } else if ("boss_relic".equals(scene)) {
            renderBossRelicBadges(sb, result, matched);
        } else {
            return;
        }
        lastBadgeMatches = matched.size();
        lastBadgeUnmatched = Math.max(0, result.optionScoreCount() - matched.size());
        lastBadgeUnmatchedLabels = unmatchedLabels(result, matched);
    }

    private String unmatchedLabels(RecommendationResult result, Set<RecommendationResult.OptionScore> matched) {
        StringBuilder out = new StringBuilder();
        int count = 0;
        for (RecommendationResult.OptionScore score : result.optionScores) {
            if (matched.contains(score)) {
                continue;
            }
            if (count > 0) {
                out.append(",");
            }
            out.append(score.optionId.isEmpty() ? score.name : score.optionId);
            count++;
            if (count >= 3) {
                break;
            }
        }
        return out.toString();
    }

    private void renderCardRewardBadges(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched) {
        try {
            if (AbstractDungeon.cardRewardScreen == null || AbstractDungeon.cardRewardScreen.rewardGroup == null) {
                return;
            }
            renderCardBadges(sb, result, matched, AbstractDungeon.cardRewardScreen.rewardGroup, -34.0F * Settings.scale);
        } catch (Exception ignored) {
        }
    }

    private void renderShopBadges(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched) {
        try {
            ShopScreen shop = AbstractDungeon.shopScreen;
            if (shop == null) {
                return;
            }
            renderCardBadges(sb, result, matched, shop.coloredCards, -30.0F * Settings.scale);
            renderCardBadges(sb, result, matched, shop.colorlessCards, -30.0F * Settings.scale);
            renderShopRelicBadges(sb, result, matched, shop);
            renderShopPotionBadges(sb, result, matched, shop);
            renderShopPurgeBadge(sb, result, matched, shop);
        } catch (Exception ignored) {
        }
    }

    private void renderCardBadges(
        SpriteBatch sb,
        RecommendationResult result,
        Set<RecommendationResult.OptionScore> matched,
        List<AbstractCard> cards,
        float yOffset
    ) {
        if (cards == null) {
            return;
        }
        for (AbstractCard card : cards) {
            if (card == null) {
                continue;
            }
            RecommendationResult.OptionScore score = result.findScore(card.cardID, card.name);
            if (score == null) {
                continue;
            }
            matched.add(score);
            float x = card.hb == null ? card.current_x : card.hb.cX;
            float y = card.hb == null ? card.current_y - 210.0F * Settings.scale : card.hb.cY - card.hb.height / 2.0F + yOffset;
            trackHover(score, card, card, x, y);
            renderBadge(sb, score, x, y, isTopScore(result, score));
        }
    }

    private void renderCombatRewardRelicBadges(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched) {
        try {
            if (AbstractDungeon.combatRewardScreen == null || AbstractDungeon.combatRewardScreen.rewards == null) {
                return;
            }
            for (RewardItem reward : AbstractDungeon.combatRewardScreen.rewards) {
                if (reward == null || reward.type != RewardItem.RewardType.RELIC || reward.relic == null) {
                    continue;
                }
                RecommendationResult.OptionScore score = result.findScore(relicId(reward.relic), reward.relic.name);
                if (score == null) {
                    continue;
                }
                matched.add(score);
                float[] position = positionForObject(reward, reward.relic);
                trackHover(score, reward, reward.relic, position[0], position[1] - 30.0F * Settings.scale);
                renderBadge(sb, score, position[0], position[1] - 30.0F * Settings.scale, isTopScore(result, score));
            }
        } catch (Exception ignored) {
        }
    }

    private void renderBossRelicBadges(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched) {
        try {
            if (AbstractDungeon.bossRelicScreen == null || AbstractDungeon.bossRelicScreen.relics == null) {
                return;
            }
            for (AbstractRelic relic : AbstractDungeon.bossRelicScreen.relics) {
                if (relic == null) {
                    continue;
                }
                RecommendationResult.OptionScore score = result.findScore(relicId(relic), relic.name);
                if (score == null) {
                    continue;
                }
                matched.add(score);
                float[] position = positionForObject(relic, relic);
                trackHover(score, relic, relic, position[0], position[1] - 44.0F * Settings.scale);
                renderBadge(sb, score, position[0], position[1] - 44.0F * Settings.scale, isTopScore(result, score));
            }
        } catch (Exception ignored) {
        }
    }

    private void renderShopRelicBadges(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched, ShopScreen shop) {
        for (Object item : iterableField(shop, "relics")) {
            AbstractRelic relic = item instanceof AbstractRelic ? (AbstractRelic) item : null;
            if (relic == null) {
                Object value = objectField(item, "relic");
                if (value instanceof AbstractRelic) {
                    relic = (AbstractRelic) value;
                }
            }
            if (relic == null) {
                continue;
            }
            RecommendationResult.OptionScore score = result.findScore(relicId(relic), relic.name);
            if (score == null) {
                continue;
            }
            matched.add(score);
            float[] position = positionForObject(item, relic);
            trackHover(score, item, relic, position[0], position[1] - 34.0F * Settings.scale);
            renderBadge(sb, score, position[0], position[1] - 34.0F * Settings.scale, isTopScore(result, score));
        }
    }

    private void renderShopPotionBadges(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched, ShopScreen shop) {
        for (Object item : iterableField(shop, "potions")) {
            AbstractPotion potion = item instanceof AbstractPotion ? (AbstractPotion) item : null;
            if (potion == null) {
                Object value = objectField(item, "potion");
                if (value instanceof AbstractPotion) {
                    potion = (AbstractPotion) value;
                }
            }
            if (potion == null) {
                continue;
            }
            RecommendationResult.OptionScore score = result.findScore(potion.ID, potion.name);
            if (score == null) {
                continue;
            }
            matched.add(score);
            float[] position = positionForObject(item, potion);
            trackHover(score, item, potion, position[0], position[1] - 34.0F * Settings.scale);
            renderBadge(sb, score, position[0], position[1] - 34.0F * Settings.scale, isTopScore(result, score));
        }
    }

    private void renderShopPurgeBadge(SpriteBatch sb, RecommendationResult result, Set<RecommendationResult.OptionScore> matched, ShopScreen shop) {
        if (!shop.purgeAvailable) {
            return;
        }
        RecommendationResult.OptionScore score = result.findScore("remove_card", "Remove a Card");
        if (score == null) {
            return;
        }
        matched.add(score);
        float x = Settings.WIDTH * 0.77F;
        float y = Settings.HEIGHT * 0.18F;
        trackHover(score, null, null, x, y);
        renderBadge(sb, score, x, y, isTopScore(result, score));
    }

    private void renderBadge(SpriteBatch sb, RecommendationResult.OptionScore score, float centerX, float centerY, boolean top) {
        String label = score.displayBadge();
        if (label.isEmpty()) {
            return;
        }
        float scale = Settings.scale;
        label = clamp(label, 8);
        float width = Math.max(58.0F * scale, Math.min(98.0F * scale, textWidth(FontHelper.topPanelInfoFont, label) + 18.0F * scale));
        float height = 24.0F * scale;
        float x = centerX - width / 2.0F;
        float y = centerY - height / 2.0F;
        Color previous = sb.getColor().cpy();
        if (score.hasRisk()) {
            sb.setColor(new Color(0.65F, 0.12F, 0.12F, 0.92F));
        } else if (top) {
            sb.setColor(new Color(0.10F, 0.48F, 0.22F, 0.94F));
        } else {
            sb.setColor(new Color(0.05F, 0.07F, 0.10F, 0.86F));
        }
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y, width, height);
        sb.setColor(top ? Settings.GOLD_COLOR : Settings.CREAM_COLOR);
        FontHelper.renderFontLeftTopAligned(
            sb,
            FontHelper.topPanelInfoFont,
            label,
            x + 8.0F * scale,
            y + height - 5.0F * scale,
            top ? Settings.GOLD_COLOR : Settings.CREAM_COLOR
        );
        sb.setColor(previous);
    }

    private void trackHover(RecommendationResult.OptionScore score, Object owner, Object fallback, float centerX, float centerY) {
        if (score == null) {
            return;
        }
        if (isHovered(owner) || isHovered(fallback) || mouseNear(centerX, centerY, 118.0F * Settings.scale, 40.0F * Settings.scale)) {
            hoveredOption = score;
        }
    }

    private boolean isHovered(Object owner) {
        if (owner == null) {
            return false;
        }
        Object hb = objectField(owner, "hb");
        if (hb == null) {
            hb = owner;
        }
        return booleanField(hb, "hovered", false);
    }

    private boolean mouseNear(float centerX, float centerY, float width, float height) {
        return InputHelper.mX >= centerX - width / 2.0F
            && InputHelper.mX <= centerX + width / 2.0F
            && InputHelper.mY >= centerY - height / 2.0F
            && InputHelper.mY <= centerY + height / 2.0F;
    }

    private void renderHoveredOptionDetail(SpriteBatch sb) {
        if (hoveredOption == null) {
            return;
        }
        float scale = Settings.scale;
        float width = 360.0F * scale;
        float height = hoverDetailHeight(hoveredOption);
        float x = InputHelper.mX + 18.0F * scale;
        if (x + width > Settings.WIDTH - 16.0F * scale) {
            x = InputHelper.mX - width - 18.0F * scale;
        }
        x = Math.max(16.0F * scale, x);
        float y = InputHelper.mY + 18.0F * scale;
        if (y + height > Settings.HEIGHT - 16.0F * scale) {
            y = InputHelper.mY - height - 18.0F * scale;
        }
        y = Math.max(16.0F * scale, y);

        Color previous = sb.getColor().cpy();
        sb.setColor(new Color(0.02F, 0.04F, 0.07F, 0.92F));
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y, width, height);
        sb.setColor(hoveredOption.hasRisk() ? new Color(0.65F, 0.12F, 0.12F, 0.96F) : new Color(0.10F, 0.48F, 0.22F, 0.96F));
        sb.draw(ImageMaster.WHITE_SQUARE_IMG, x, y + height - 4.0F * scale, width, 4.0F * scale);
        sb.setColor(previous);

        float padding = 12.0F * scale;
        float textX = x + padding;
        float cursorY = y + height - padding;
        float contentWidth = width - padding * 2.0F;
        cursorY = renderWrappedLines(
            sb,
            clamp(hoveredOption.displayName(chineseVisible), chineseVisible ? 32 : 58),
            textX,
            cursorY,
            contentWidth,
            1,
            22.0F * scale,
            Settings.GOLD_COLOR,
            true
        );
        FontHelper.renderFontLeftTopAligned(
            sb,
            FontHelper.topPanelInfoFont,
            optionMetricsText(hoveredOption),
            textX,
            cursorY - 2.0F * scale,
            Settings.GREEN_TEXT_COLOR
        );
        cursorY -= 24.0F * scale;

        String reason = hoveredOption.reason(chineseVisible);
        if (!reason.isEmpty()) {
            cursorY = renderWrappedLines(
                sb,
                clamp(reason, chineseVisible ? 92 : 150),
                textX,
                cursorY,
                contentWidth,
                2,
                19.0F * scale,
                Settings.CREAM_COLOR
            );
        }
        String risk = hoveredOption.risk(chineseVisible);
        if (!risk.isEmpty()) {
            renderWrappedLines(
                sb,
                riskLabel() + clamp(risk, chineseVisible ? 50 : 82),
                textX,
                cursorY - 2.0F * scale,
                contentWidth,
                2,
                18.0F * scale,
                Settings.RED_TEXT_COLOR
            );
        }
    }

    private float hoverDetailHeight(RecommendationResult.OptionScore score) {
        float scale = Settings.scale;
        float height = 104.0F * scale;
        if (!score.reason(chineseVisible).isEmpty()) {
            height += 42.0F * scale;
        }
        if (!score.risk(chineseVisible).isEmpty()) {
            height += 38.0F * scale;
        }
        return Math.min(190.0F * scale, height);
    }

    private String optionMetricsText(RecommendationResult.OptionScore score) {
        String text;
        if (chineseVisible) {
            text = "分数 " + score.score + " | 置信度 " + score.confidence;
            if (!score.shopPrice.isEmpty()) {
                text += " | 价格 " + score.shopPrice + " 金";
                text += score.shopAffordable ? " | 可购买" : " | 金币不足";
            }
            return text;
        }
        text = "Score " + score.score + " | Confidence " + score.confidence;
        if (!score.shopPrice.isEmpty()) {
            text += " | " + score.shopPrice + "g";
            text += score.shopAffordable ? " | affordable" : " | cannot afford";
        }
        return text;
    }

    private boolean isTopScore(RecommendationResult result, RecommendationResult.OptionScore score) {
        return result != null && !result.optionScores.isEmpty() && result.optionScores.get(0) == score;
    }

    private String relicId(AbstractRelic relic) {
        return relic.relicId == null ? relic.name : relic.relicId;
    }

    private float[] positionForObject(Object owner, Object fallback) {
        float[] hitbox = hitboxCenter(owner);
        if (hitbox != null) {
            return hitbox;
        }
        hitbox = hitboxCenter(fallback);
        if (hitbox != null) {
            return hitbox;
        }
        float x = floatField(owner, "currentX", Float.NaN);
        float y = floatField(owner, "currentY", Float.NaN);
        if (Float.isNaN(x) || Float.isNaN(y)) {
            x = floatField(fallback, "currentX", Settings.WIDTH / 2.0F);
            y = floatField(fallback, "currentY", Settings.HEIGHT / 2.0F);
        }
        return new float[] {x, y};
    }

    private float[] hitboxCenter(Object owner) {
        Object hb = objectField(owner, "hb");
        if (hb == null) {
            return null;
        }
        float x = floatField(hb, "cX", Float.NaN);
        float y = floatField(hb, "cY", Float.NaN);
        if (Float.isNaN(x) || Float.isNaN(y)) {
            return null;
        }
        return new float[] {x, y};
    }

    private List<Object> iterableField(Object owner, String fieldName) {
        java.util.ArrayList<Object> values = new java.util.ArrayList<Object>();
        Object fieldValue = objectField(owner, fieldName);
        if (fieldValue instanceof Iterable) {
            for (Object item : (Iterable<?>) fieldValue) {
                if (item != null) {
                    values.add(item);
                }
            }
        }
        return values;
    }

    private Object objectField(Object owner, String fieldName) {
        if (owner == null) {
            return null;
        }
        Class<?> type = owner.getClass();
        while (type != null) {
            try {
                java.lang.reflect.Field field = type.getDeclaredField(fieldName);
                field.setAccessible(true);
                return field.get(owner);
            } catch (Exception ignored) {
                type = type.getSuperclass();
            }
        }
        return null;
    }

    private float floatField(Object owner, String fieldName, float fallback) {
        Object value = objectField(owner, fieldName);
        if (value instanceof Number) {
            return ((Number) value).floatValue();
        }
        return fallback;
    }

    private boolean booleanField(Object owner, String fieldName, boolean fallback) {
        Object value = objectField(owner, fieldName);
        if (value instanceof Boolean) {
            return ((Boolean) value).booleanValue();
        }
        return fallback;
    }

    private float panelHeight(boolean hasFreshRecommendation) {
        float scale = Settings.scale;
        if (!hasFreshRecommendation) {
            return 84.0F * scale;
        }
        float height = latest.risk(chineseVisible).isEmpty() ? 190.0F * scale : 224.0F * scale;
        height += 22.0F * scale;
        if (debugVisible) {
            height += latest.whyNot.isEmpty() ? 48.0F * scale : 84.0F * scale;
        }
        return height;
    }

    private float renderWrappedLines(
        SpriteBatch sb,
        String text,
        float x,
        float y,
        float maxWidth,
        int maxLines,
        float lineHeight,
        Color color
    ) {
        return renderWrappedLines(sb, text, x, y, maxWidth, maxLines, lineHeight, color, false);
    }

    private float renderWrappedLines(
        SpriteBatch sb,
        String text,
        float x,
        float y,
        float maxWidth,
        int maxLines,
        float lineHeight,
        Color color,
        boolean header
    ) {
        if (text == null || text.isEmpty()) {
            return y;
        }
        BitmapFont font = header ? FontHelper.tipHeaderFont : FontHelper.tipBodyFont;
        java.util.List<String> lines = wrapText(text, font, maxWidth, maxLines);
        float cursor = y;
        for (String line : lines) {
            FontHelper.renderFontLeftTopAligned(
                sb,
                font,
                line,
                x,
                cursor,
                color
            );
            cursor -= lineHeight;
        }
        return cursor;
    }

    private java.util.List<String> wrapText(String text, BitmapFont font, float maxWidth, int maxLines) {
        java.util.ArrayList<String> lines = new java.util.ArrayList<String>();
        String remaining = text == null ? "" : text.trim();
        while (!remaining.isEmpty() && lines.size() < maxLines) {
            if (textWidth(font, remaining) <= maxWidth) {
                lines.add(remaining);
                return lines;
            }
            int cut = findWrapCut(remaining, font, maxWidth);
            String line = remaining.substring(0, cut).trim();
            if (line.isEmpty()) {
                line = remaining.substring(0, Math.min(1, remaining.length()));
                cut = line.length();
            }
            remaining = remaining.substring(cut).trim();
            if (lines.size() == maxLines - 1 && !remaining.isEmpty()) {
                line = ellipsizeToWidth(line, font, maxWidth);
                lines.add(line);
                return lines;
            }
            lines.add(line);
        }
        return lines;
    }

    private int findWrapCut(String text, BitmapFont font, float maxWidth) {
        int best = 1;
        int lastSpace = -1;
        for (int i = 1; i <= text.length(); i++) {
            char c = text.charAt(i - 1);
            if (Character.isWhitespace(c)) {
                lastSpace = i - 1;
            }
            if (textWidth(font, text.substring(0, i)) > maxWidth) {
                if (lastSpace > 8) {
                    return lastSpace;
                }
                return Math.max(1, best);
            }
            best = i;
        }
        return best;
    }

    private String ellipsizeToWidth(String text, BitmapFont font, float maxWidth) {
        String suffix = "...";
        String value = text == null ? "" : text.trim();
        while (!value.isEmpty() && textWidth(font, value + suffix) > maxWidth) {
            value = value.substring(0, value.length() - 1).trim();
        }
        return value.isEmpty() ? suffix : value + suffix;
    }

    private float textWidth(BitmapFont font, String text) {
        GlyphLayout layout = new GlyphLayout();
        layout.setText(font, text == null ? "" : text);
        return layout.width;
    }

    private String panelTitle() {
        return chineseVisible ? "STS 助手  |  F10 English  |  F11 流派" : "STS Agent  |  F10 中文  |  F11 Target";
    }

    private String riskLabel() {
        return chineseVisible ? "风险：" : "Risk: ";
    }

    private String metricsText() {
        if (chineseVisible) {
            return "分数 " + latest.score + " | 置信度 " + latest.confidence;
        }
        return "Score " + latest.score + " | Confidence " + latest.confidence;
    }

    private String targetText() {
        if (chineseVisible) {
            return "目标流派：" + archetypeDisplayName(preferredArchetype, true);
        }
        return "Target: " + archetypeDisplayName(preferredArchetype, false);
    }

    private String archetypeDisplayName(String archetypeId, boolean chinese) {
        if (archetypeId == null || archetypeId.isEmpty()) {
            return chinese ? "自动检测" : "Auto";
        }
        if ("silent_poison".equals(archetypeId)) {
            return chinese ? "猎手毒流" : "Silent Poison";
        }
        if ("silent_shiv".equals(archetypeId)) {
            return chinese ? "猎手刀片流" : "Silent Shiv";
        }
        if ("silent_discard".equals(archetypeId)) {
            return chinese ? "猎手弃牌流" : "Silent Discard";
        }
        if ("silent_wraith_form".equals(archetypeId)) {
            return chinese ? "猎手幽魂防御" : "Silent Wraith Form";
        }
        if ("silent_grand_finale".equals(archetypeId)) {
            return chinese ? "猎手华丽收场" : "Silent Grand Finale";
        }
        if ("ironclad_strength".equals(archetypeId)) {
            return chinese ? "铁甲力量流" : "Ironclad Strength";
        }
        if ("ironclad_exhaust".equals(archetypeId)) {
            return chinese ? "铁甲消耗流" : "Ironclad Exhaust";
        }
        if ("ironclad_block_barricade".equals(archetypeId)) {
            return chinese ? "铁甲壁垒格挡" : "Ironclad Barricade";
        }
        if ("ironclad_self_damage".equals(archetypeId)) {
            return chinese ? "铁甲自残流" : "Ironclad Self Damage";
        }
        if ("ironclad_searing_blow".equals(archetypeId)) {
            return chinese ? "铁甲灼热攻击" : "Ironclad Searing Blow";
        }
        if ("defect_frost_focus".equals(archetypeId)) {
            return chinese ? "故障机器人冰球集中" : "Defect Frost Focus";
        }
        if ("defect_lightning".equals(archetypeId)) {
            return chinese ? "故障机器人闪电流" : "Defect Lightning";
        }
        if ("defect_dark_orb".equals(archetypeId)) {
            return chinese ? "故障机器人黑球流" : "Defect Dark Orb";
        }
        if ("defect_power".equals(archetypeId)) {
            return chinese ? "故障机器人能力流" : "Defect Power";
        }
        if ("defect_claw_zero_cost".equals(archetypeId)) {
            return chinese ? "故障机器人爪击零费" : "Defect Claw";
        }
        if ("watcher_stance_dance".equals(archetypeId)) {
            return chinese ? "观者姿态切换" : "Watcher Stance Dance";
        }
        if ("watcher_wrath_burst".equals(archetypeId)) {
            return chinese ? "观者愤怒爆发" : "Watcher Wrath Burst";
        }
        if ("watcher_divinity".equals(archetypeId)) {
            return chinese ? "观者神格真言" : "Watcher Divinity";
        }
        if ("watcher_retain".equals(archetypeId)) {
            return chinese ? "观者保留流" : "Watcher Retain";
        }
        if ("watcher_pressure_points".equals(archetypeId)) {
            return chinese ? "观者点穴流" : "Watcher Pressure Points";
        }
        return archetypeId;
    }

    private String badgeText() {
        if (!latest.displayBadge.isEmpty()) {
            return latest.displayBadge;
        }
        if (!latest.grade.isEmpty()) {
            return latest.grade + " " + latest.score;
        }
        return latest.score;
    }

    private String sceneDisplayName(String sceneType) {
        if ("card_reward".equals(sceneType)) {
            return chineseVisible ? "选牌奖励" : "Card Reward";
        }
        if ("relic_reward".equals(sceneType)) {
            return chineseVisible ? "遗物奖励" : "Relic Reward";
        }
        if ("boss_relic".equals(sceneType)) {
            return chineseVisible ? "Boss 遗物" : "Boss Relic";
        }
        if ("shop".equals(sceneType)) {
            return chineseVisible ? "商店" : "Shop";
        }
        if ("map".equals(sceneType)) {
            return chineseVisible ? "地图" : "Map";
        }
        if ("combat".equals(sceneType)) {
            return chineseVisible ? "战斗" : "Combat";
        }
        return sceneType;
    }

    private String clamp(String text, int maxLength) {
        if (text == null || text.length() <= maxLength) {
            return text == null ? "" : text;
        }
        return text.substring(0, maxLength - 3) + "...";
    }
}
