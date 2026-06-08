package com.stsagent.bridge;

public final class RecommendationParser {
    private RecommendationParser() {
    }

    public static RecommendationResult parse(String responseBody) {
        if (responseBody == null || responseBody.isEmpty()) {
            return null;
        }
        String recommendationBlock = objectForKey(responseBody, "recommendation");
        if (recommendationBlock.isEmpty()) {
            return null;
        }

        String optionId = stringValue(recommendationBlock, "recommendation");
        String sceneType = stringValue(recommendationBlock, "scene_type");
        String debugBlock = objectForKey(recommendationBlock, "debug");
        String scoreBlock = firstObjectInArray(recommendationBlock, "option_scores");
        String name = stringValue(scoreBlock, "name");
        String score = rawValue(scoreBlock, "score");
        String confidence = rawValue(scoreBlock, "confidence");
        String grade = stringValue(scoreBlock, "grade");
        String displayBadge = stringValue(scoreBlock, "display_badge");
        String whyNot = stringValue(scoreBlock, "why_not");
        String reason = firstStringInArray(scoreBlock, "reasons");
        String risk = firstStringInArray(scoreBlock, "risks");
        String debugSummary = debugSummary(debugBlock);
        return new RecommendationResult(optionId, name, reason, risk, score, confidence, sceneType, grade, displayBadge, whyNot, debugSummary);
    }

    private static String debugSummary(String debugBlock) {
        if (debugBlock == null || debugBlock.isEmpty()) {
            return "";
        }
        String queryType = stringValue(debugBlock, "query_type");
        String sceneType = stringValue(debugBlock, "scene_type");
        String optionsCount = rawValue(debugBlock, "options_count");
        String latency = rawValue(debugBlock, "latency_ms");
        return "scene=" + sceneType + " query=" + queryType + " options=" + optionsCount + " latency=" + latency + "ms";
    }

    private static String objectForKey(String json, String key) {
        int keyIndex = json.indexOf("\"" + key + "\"");
        if (keyIndex < 0) {
            return "";
        }
        int colon = json.indexOf(":", keyIndex);
        int start = json.indexOf("{", colon);
        if (colon < 0 || start < 0) {
            return "";
        }
        int end = matching(json, start, '{', '}');
        return end < 0 ? "" : json.substring(start, end + 1);
    }

    private static String firstObjectInArray(String json, String key) {
        int keyIndex = json.indexOf("\"" + key + "\"");
        if (keyIndex < 0) {
            return "";
        }
        int arrayStart = json.indexOf("[", keyIndex);
        int objectStart = json.indexOf("{", arrayStart);
        if (arrayStart < 0 || objectStart < 0) {
            return "";
        }
        int end = matching(json, objectStart, '{', '}');
        return end < 0 ? "" : json.substring(objectStart, end + 1);
    }

    private static String firstStringInArray(String json, String key) {
        int keyIndex = json.indexOf("\"" + key + "\"");
        if (keyIndex < 0) {
            return "";
        }
        int arrayStart = json.indexOf("[", keyIndex);
        if (arrayStart < 0) {
            return "";
        }
        int valueStart = json.indexOf("\"", arrayStart);
        if (valueStart < 0) {
            return "";
        }
        int valueEnd = stringEnd(json, valueStart + 1);
        return valueEnd < 0 ? "" : unescape(json.substring(valueStart + 1, valueEnd));
    }

    private static String stringValue(String json, String key) {
        int keyIndex = json.indexOf("\"" + key + "\"");
        if (keyIndex < 0) {
            return "";
        }
        int colon = json.indexOf(":", keyIndex);
        int start = json.indexOf("\"", colon);
        if (colon < 0 || start < 0) {
            return "";
        }
        int end = stringEnd(json, start + 1);
        return end < 0 ? "" : unescape(json.substring(start + 1, end));
    }

    private static String rawValue(String json, String key) {
        int keyIndex = json.indexOf("\"" + key + "\"");
        if (keyIndex < 0) {
            return "";
        }
        int colon = json.indexOf(":", keyIndex);
        if (colon < 0) {
            return "";
        }
        int start = colon + 1;
        while (start < json.length() && Character.isWhitespace(json.charAt(start))) {
            start++;
        }
        int end = start;
        while (end < json.length() && ",}]".indexOf(json.charAt(end)) < 0) {
            end++;
        }
        return json.substring(start, end).replace("\"", "").trim();
    }

    private static int matching(String text, int start, char open, char close) {
        int depth = 0;
        boolean inString = false;
        boolean escaped = false;
        for (int i = start; i < text.length(); i++) {
            char c = text.charAt(i);
            if (inString) {
                if (escaped) {
                    escaped = false;
                } else if (c == '\\') {
                    escaped = true;
                } else if (c == '"') {
                    inString = false;
                }
                continue;
            }
            if (c == '"') {
                inString = true;
            } else if (c == open) {
                depth++;
            } else if (c == close) {
                depth--;
                if (depth == 0) {
                    return i;
                }
            }
        }
        return -1;
    }

    private static int stringEnd(String text, int start) {
        boolean escaped = false;
        for (int i = start; i < text.length(); i++) {
            char c = text.charAt(i);
            if (escaped) {
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else if (c == '"') {
                return i;
            }
        }
        return -1;
    }

    private static String unescape(String value) {
        StringBuilder out = new StringBuilder(value.length());
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c == '\\' && i + 1 < value.length()) {
                char next = value.charAt(++i);
                switch (next) {
                    case '"':
                    case '\\':
                    case '/':
                        out.append(next);
                        break;
                    case 'n':
                        out.append(' ');
                        break;
                    case 't':
                    case 'r':
                        out.append(' ');
                        break;
                    default:
                        out.append(next);
                }
            } else {
                out.append(c);
            }
        }
        return out.toString();
    }
}
