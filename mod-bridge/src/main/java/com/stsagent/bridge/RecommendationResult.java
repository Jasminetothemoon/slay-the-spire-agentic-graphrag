package com.stsagent.bridge;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class RecommendationResult {
    public static class OptionScore {
        public final String optionId;
        public final String name;
        public final String score;
        public final String confidence;
        public final String grade;
        public final String displayBadge;
        public final String whyNot;
        public final String reason;
        public final String risk;
        public final String zhName;
        public final String zhReason;
        public final String zhRisk;

        public OptionScore(
            String optionId,
            String name,
            String score,
            String confidence,
            String grade,
            String displayBadge,
            String whyNot,
            String reason,
            String risk,
            String zhName,
            String zhReason,
            String zhRisk
        ) {
            this.optionId = valueOrEmpty(optionId);
            this.name = valueOrEmpty(name);
            this.score = valueOrEmpty(score);
            this.confidence = valueOrEmpty(confidence);
            this.grade = valueOrEmpty(grade);
            this.displayBadge = valueOrEmpty(displayBadge);
            this.whyNot = valueOrEmpty(whyNot);
            this.reason = valueOrEmpty(reason);
            this.risk = valueOrEmpty(risk);
            this.zhName = valueOrEmpty(zhName);
            this.zhReason = valueOrEmpty(zhReason);
            this.zhRisk = valueOrEmpty(zhRisk);
        }

        public String displayBadge() {
            if (!displayBadge.isEmpty()) {
                return displayBadge;
            }
            if (!grade.isEmpty()) {
                return grade + " " + score;
            }
            return score;
        }

        public boolean hasRisk() {
            return !risk.isEmpty();
        }

        public String displayName(boolean chinese) {
            return chinese && !zhName.isEmpty() ? zhName : name;
        }

        public String reason(boolean chinese) {
            return chinese && !zhReason.isEmpty() ? zhReason : reason;
        }

        public String risk(boolean chinese) {
            return chinese && !zhRisk.isEmpty() ? zhRisk : risk;
        }
    }

    public final String optionId;
    public final String name;
    public final String reason;
    public final String risk;
    public final String score;
    public final String confidence;
    public final String sceneType;
    public final String grade;
    public final String displayBadge;
    public final String whyNot;
    public final String debugSummary;
    public final String localizedReasoning;
    public final String localizedRecommendationName;
    public final List<OptionScore> optionScores;
    public final long receivedAt;

    public RecommendationResult(String optionId, String name, String reason, String risk, String score, String confidence) {
        this(optionId, name, reason, risk, score, confidence, "", "", "", "", "", "", "", new ArrayList<OptionScore>());
    }

    public RecommendationResult(
        String optionId,
        String name,
        String reason,
        String risk,
        String score,
        String confidence,
        String sceneType,
        String grade,
        String displayBadge,
        String whyNot,
        String debugSummary,
        String localizedReasoning,
        String localizedRecommendationName,
        List<OptionScore> optionScores
    ) {
        this.optionId = valueOrEmpty(optionId);
        this.name = valueOrEmpty(name);
        this.reason = valueOrEmpty(reason);
        this.risk = valueOrEmpty(risk);
        this.score = valueOrEmpty(score);
        this.confidence = valueOrEmpty(confidence);
        this.sceneType = valueOrEmpty(sceneType);
        this.grade = valueOrEmpty(grade);
        this.displayBadge = valueOrEmpty(displayBadge);
        this.whyNot = valueOrEmpty(whyNot);
        this.debugSummary = valueOrEmpty(debugSummary);
        this.localizedReasoning = valueOrEmpty(localizedReasoning);
        this.localizedRecommendationName = valueOrEmpty(localizedRecommendationName);
        this.optionScores = Collections.unmodifiableList(new ArrayList<OptionScore>(optionScores == null ? new ArrayList<OptionScore>() : optionScores));
        this.receivedAt = System.currentTimeMillis();
    }

    public boolean hasContent() {
        return !name.isEmpty() || !optionId.isEmpty();
    }

    public String displayName() {
        return name.isEmpty() ? optionId : name;
    }

    public String displayName(boolean chinese) {
        if (chinese && !localizedRecommendationName.isEmpty()) {
            return localizedRecommendationName;
        }
        if (chinese && !optionScores.isEmpty() && !optionScores.get(0).zhName.isEmpty()) {
            return optionScores.get(0).zhName;
        }
        return displayName();
    }

    public String reason(boolean chinese) {
        if (chinese && !localizedReasoning.isEmpty()) {
            return localizedReasoning;
        }
        if (chinese && !optionScores.isEmpty() && !optionScores.get(0).zhReason.isEmpty()) {
            return optionScores.get(0).zhReason;
        }
        return reason;
    }

    public String risk(boolean chinese) {
        if (chinese && !optionScores.isEmpty() && !optionScores.get(0).zhRisk.isEmpty()) {
            return optionScores.get(0).zhRisk;
        }
        return risk;
    }

    public OptionScore findScore(String primary, String fallback) {
        String primaryKey = normalizeKey(primary);
        String fallbackKey = normalizeKey(fallback);
        for (OptionScore score : optionScores) {
            if (matches(score, primaryKey) || matches(score, fallbackKey)) {
                return score;
            }
        }
        return null;
    }

    public int optionScoreCount() {
        return optionScores.size();
    }

    private static boolean matches(OptionScore score, String key) {
        return !key.isEmpty()
            && (key.equals(normalizeKey(score.optionId)) || key.equals(normalizeKey(score.name)));
    }

    private static String normalizeKey(String value) {
        if (value == null) {
            return "";
        }
        StringBuilder out = new StringBuilder(value.length());
        for (int i = 0; i < value.length(); i++) {
            char c = Character.toLowerCase(value.charAt(i));
            if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) {
                out.append(c);
            }
        }
        return out.toString();
    }

    private static String valueOrEmpty(String value) {
        return value == null ? "" : value;
    }
}
