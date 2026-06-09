package com.stsagent.bridge;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.text.SimpleDateFormat;
import java.util.Date;

public class BridgeCaptureLogger {
    private final BridgeConfig config;
    private final File outputFile;

    public BridgeCaptureLogger(BridgeConfig config) {
        this.config = config;
        if (config.capture) {
            File directory = new File(config.captureDir);
            if (!directory.exists()) {
                directory.mkdirs();
            }
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss").format(new Date());
            this.outputFile = new File(directory, stamp + "-" + config.runId + ".jsonl");
        } else {
            this.outputFile = null;
        }
    }

    public void recordRecommendation(BridgePayload payload, RecommendationResult result, String screen, long latencyMs, String error) {
        if (!config.capture || outputFile == null) {
            return;
        }
        String top = result == null ? "" : result.displayName();
        String scene = result == null ? "" : result.sceneType;
        String line = "{"
            + "\"timestamp\":" + System.currentTimeMillis() + ","
            + "\"kind\":\"recommendation\","
            + "\"screen\":\"" + JsonUtil.escape(screen) + "\","
            + "\"query_type\":\"" + JsonUtil.escape(payload.queryType()) + "\","
            + "\"options_count\":" + payload.options().size() + ","
            + "\"options\":" + JsonUtil.stringArray(payload.options()) + ","
            + "\"state\":" + payload.stateJson() + ","
            + "\"response_summary\":{"
            + "\"scene_type\":\"" + JsonUtil.escape(scene) + "\","
            + "\"top_recommendation\":\"" + JsonUtil.escape(top) + "\","
            + "\"latency_ms\":" + latencyMs + ","
            + "\"error\":\"" + JsonUtil.escape(error) + "\""
            + "}"
            + "}";
        append(line);
    }

    public void recordState(String stateJson, String screen, String error) {
        if (!config.capture || outputFile == null) {
            return;
        }
        String line = "{"
            + "\"timestamp\":" + System.currentTimeMillis() + ","
            + "\"kind\":\"state\","
            + "\"screen\":\"" + JsonUtil.escape(screen) + "\","
            + "\"state\":" + stateJson + ","
            + "\"error\":\"" + JsonUtil.escape(error) + "\""
            + "}";
        append(line);
    }

    private void append(String line) {
        try (PrintWriter writer = new PrintWriter(new FileWriter(outputFile, true))) {
            writer.println(line);
        } catch (Exception ex) {
            if (config.verbose) {
                System.out.println("[STS Agent Bridge] Capture failed: " + ex.getMessage());
            }
        }
    }
}
