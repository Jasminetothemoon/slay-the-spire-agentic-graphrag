package com.stsagent.bridge;

public class BridgeConfig {
    public final String apiBaseUrl;
    public final String runId;
    public final boolean verbose;
    public final boolean capture;
    public final String captureDir;
    public final String preferredArchetype;

    private BridgeConfig(String apiBaseUrl, String runId, boolean verbose, boolean capture, String captureDir, String preferredArchetype) {
        this.apiBaseUrl = trimTrailingSlash(apiBaseUrl);
        this.runId = runId;
        this.verbose = verbose;
        this.capture = capture;
        this.captureDir = captureDir;
        this.preferredArchetype = normalizeArchetype(preferredArchetype);
    }

    public static BridgeConfig fromRuntime() {
        String apiBaseUrl = firstNonBlank(
            System.getProperty("sts.agent.apiUrl"),
            System.getenv("STS_AGENT_API_URL"),
            "http://127.0.0.1:8000"
        );
        String runId = firstNonBlank(
            System.getProperty("sts.agent.runId"),
            System.getenv("STS_AGENT_RUN_ID"),
            "mod_live"
        );
        boolean verbose = Boolean.parseBoolean(firstNonBlank(
            System.getProperty("sts.agent.verbose"),
            System.getenv("STS_AGENT_VERBOSE"),
            "false"
        ));
        boolean capture = Boolean.parseBoolean(firstNonBlank(
            System.getProperty("sts.agent.capture"),
            System.getenv("STS_AGENT_CAPTURE"),
            "false"
        ));
        String captureDir = firstNonBlank(
            System.getProperty("sts.agent.captureDir"),
            System.getenv("STS_AGENT_CAPTURE_DIR"),
            "artifacts/mod_payloads"
        );
        String preferredArchetype = firstNonBlank(
            System.getProperty("sts.agent.archetype"),
            System.getenv("STS_AGENT_ARCHETYPE"),
            ""
        );
        return new BridgeConfig(apiBaseUrl, runId, verbose, capture, captureDir, preferredArchetype);
    }

    private static String firstNonBlank(String first, String second, String fallback) {
        if (first != null && !first.trim().isEmpty()) {
            return first.trim();
        }
        if (second != null && !second.trim().isEmpty()) {
            return second.trim();
        }
        return fallback;
    }

    private static String trimTrailingSlash(String value) {
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        return value;
    }

    private static String normalizeArchetype(String value) {
        if (value == null) {
            return "";
        }
        String normalized = value.trim().toLowerCase().replace(" ", "_").replace("-", "_");
        if ("auto".equals(normalized) || "none".equals(normalized) || "default".equals(normalized)) {
            return "";
        }
        return normalized;
    }
}
