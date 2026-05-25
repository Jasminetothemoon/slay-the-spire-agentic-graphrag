package com.stsagent.bridge;

public class BridgeConfig {
    public final String apiBaseUrl;
    public final String runId;
    public final boolean verbose;

    private BridgeConfig(String apiBaseUrl, String runId, boolean verbose) {
        this.apiBaseUrl = trimTrailingSlash(apiBaseUrl);
        this.runId = runId;
        this.verbose = verbose;
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
        return new BridgeConfig(apiBaseUrl, runId, verbose);
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
