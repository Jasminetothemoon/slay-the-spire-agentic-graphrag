package com.stsagent.bridge;

import java.io.OutputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
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

    public RecommendationResult postRecommendation(BridgePayload payload) {
        String body = "{"
            + "\"state\":" + payload.stateJson() + ","
            + "\"query_type\":\"" + JsonUtil.escape(payload.queryType()) + "\","
            + "\"options\":" + JsonUtil.stringArray(payload.options()) + ","
            + "\"user_query\":\"" + JsonUtil.escape(payload.userQuery()) + "\""
            + "}";
        String responseBody = post("/mod/recommend", body);
        return RecommendationParser.parse(responseBody);
    }

    private String post(String path, String body) {
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
            String responseBody = readResponse(connection, status);
            if (config.verbose) {
                System.out.println("[STS Agent Bridge] POST " + path + " -> " + status);
            }
            return responseBody;
        } catch (Exception ex) {
            if (config.verbose) {
                System.out.println("[STS Agent Bridge] Failed to POST " + path + ": " + ex.getMessage());
            }
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
        return "";
    }

    private String readResponse(HttpURLConnection connection, int status) {
        InputStream stream = null;
        try {
            stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            if (stream == null) {
                return "";
            }
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[1024];
            int read;
            while ((read = stream.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
            }
            return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        } finally {
            if (stream != null) {
                try {
                    stream.close();
                } catch (Exception ignored) {
                }
            }
        }
    }
}
