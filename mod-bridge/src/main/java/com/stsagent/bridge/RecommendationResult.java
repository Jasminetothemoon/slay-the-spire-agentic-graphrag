package com.stsagent.bridge;

public class RecommendationResult {
    public final String optionId;
    public final String name;
    public final String reason;
    public final String risk;
    public final String score;
    public final String confidence;
    public final long receivedAt;

    public RecommendationResult(String optionId, String name, String reason, String risk, String score, String confidence) {
        this.optionId = valueOrEmpty(optionId);
        this.name = valueOrEmpty(name);
        this.reason = valueOrEmpty(reason);
        this.risk = valueOrEmpty(risk);
        this.score = valueOrEmpty(score);
        this.confidence = valueOrEmpty(confidence);
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
