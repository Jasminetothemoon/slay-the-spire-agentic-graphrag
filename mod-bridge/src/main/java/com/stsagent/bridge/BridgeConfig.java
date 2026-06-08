package com.stsagent.bridge;

public class BridgeConfig {
    public final String apiBaseUrl;
    public final String runId;
    public final boolean verbose;
    public final boolean capture;
    public final String captureDir;

    private BridgeConfig(String apiBaseUrl, String runId, boolean verbose, boolean capture, String captureDir) {
        this.apiBaseUrl = trimTrailingSlash(apiBaseUrl);
        this.runId = runId;
        this.verbose = verbose;
        this.capture = capture;
        this.captureDir = captureDir;
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
        return new BridgeConfig(apiBaseUrl, runId, verbose, capture, captureDir);
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
}
