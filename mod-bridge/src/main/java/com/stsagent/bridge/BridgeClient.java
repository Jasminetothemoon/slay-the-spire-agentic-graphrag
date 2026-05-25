package com.stsagent.bridge;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class BridgeClient {
    private final BridgeConfig config;

    public BridgeClient(BridgeConfig config) {
        this.config = config;
    }

    public void postState(String stateJson) {
        post("/mod/state", stateJson);
    }

    public void postRecommendation(BridgePayload payload) {
        String body = "{"
            + "\"state\":" + payload.stateJson() + ","
            + "\"query_type\":\"" + JsonUtil.escape(payload.queryType()) + "\","
            + "\"options\":" + JsonUtil.stringArray(payload.options()) + ","
            + "\"user_query\":\"" + JsonUtil.escape(payload.userQuery()) + "\""
            + "}";
        post("/mod/recommend", body);
    }

    private void post(String path, String body) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL(config.apiBaseUrl + path);
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(400);
            connection.setReadTimeout(700);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setDoOutput(true);

            byte[] payload = body.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(payload.length);
            try (OutputStream stream = connection.getOutputStream()) {
                stream.write(payload);
            }

            int status = connection.getResponseCode();
            if (config.verbose) {
                System.out.println("[STS Agent Bridge] POST " + path + " -> " + status);
            }
        } catch (Exception ex) {
            if (config.verbose) {
                System.out.println("[STS Agent Bridge] Failed to POST " + path + ": " + ex.getMessage());
            }
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }
}
