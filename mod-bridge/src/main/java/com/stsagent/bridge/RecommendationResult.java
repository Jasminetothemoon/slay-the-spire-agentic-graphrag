package com.stsagent.bridge;

public class RecommendationResult {
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
    public final long receivedAt;

    public RecommendationResult(String optionId, String name, String reason, String risk, String score, String confidence) {
        this(optionId, name, reason, risk, score, confidence, "", "", "", "", "");
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
        String debugSummary
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
        this.receivedAt = System.currentTimeMillis();
    }

    public boolean hasContent() {
        return !name.isEmpty() || !optionId.isEmpty();
    }

    public String displayName() {
        return name.isEmpty() ? optionId : name;
    }

    private static String valueOrEmpty(String value) {
        return value == null ? "" : value;
    }
}
