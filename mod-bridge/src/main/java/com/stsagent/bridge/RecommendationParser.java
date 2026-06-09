package com.stsagent.bridge;

import java.util.ArrayList;
import java.util.List;

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
        String localizedBlock = objectForKey(recommendationBlock, "localized");
        String zhBlock = objectForKey(localizedBlock, "zh");
        List<String> zhScoreBlocks = objectsInArray(zhBlock, "option_scores");
        List<RecommendationResult.OptionScore> optionScores = optionScores(recommendationBlock, zhScoreBlocks);
        RecommendationResult.OptionScore top = optionScores.isEmpty()
            ? new RecommendationResult.OptionScore("", "", "", "", "", "", "", "", "", "", "", "", "", "", true)
            : optionScores.get(0);
        String name = top.name;
        String score = top.score;
        String confidence = top.confidence;
        String grade = top.grade;
        String displayBadge = top.displayBadge;
        String whyNot = top.whyNot;
        String reason = top.reason;
        String risk = top.risk;
        String debugSummary = debugSummary(debugBlock);
        return new RecommendationResult(
            optionId,
            name,
            reason,
            risk,
            score,
            confidence,
            sceneType,
            grade,
            displayBadge,
            whyNot,
            debugSummary,
            stringValue(zhBlock, "reasoning"),
            stringValue(zhBlock, "recommendation_name"),
            optionScores
        );
    }

    private static List<RecommendationResult.OptionScore> optionScores(String recommendationBlock, List<String> zhScoreBlocks) {
        List<RecommendationResult.OptionScore> scores = new ArrayList<RecommendationResult.OptionScore>();
        int index = 0;
        for (String scoreBlock : objectsInArray(recommendationBlock, "option_scores")) {
            String zhBlock = index < zhScoreBlocks.size() ? zhScoreBlocks.get(index) : "";
            scores.add(
                new RecommendationResult.OptionScore(
                    stringValue(scoreBlock, "option_id"),
                    stringValue(scoreBlock, "name"),
                    rawValue(scoreBlock, "score"),
                    rawValue(scoreBlock, "confidence"),
                    stringValue(scoreBlock, "grade"),
                    stringValue(scoreBlock, "display_badge"),
                    stringValue(scoreBlock, "why_not"),
                    firstStringInArray(scoreBlock, "reasons"),
                    firstStringInArray(scoreBlock, "risks"),
                    stringValue(zhBlock, "name"),
                    firstStringInArray(zhBlock, "reasons"),
                    firstStringInArray(zhBlock, "risks"),
                    stringValue(scoreBlock, "shop_item_type"),
                    rawValue(scoreBlock, "shop_price"),
                    booleanValue(scoreBlock, "shop_affordable", true)
                )
            );
            index++;
        }
        return scores;
    }

    private static String debugSummary(String debugBlock) {
        if (debugBlock == null || debugBlock.isEmpty()) {
            return "";
        }
        String queryType = stringValue(debugBlock, "query_type");
        String sceneType = stringValue(debugBlock, "scene_type");
        String selectedSkill = stringValue(debugBlock, "selected_skill");
        String optionsCount = rawValue(debugBlock, "options_count");
        String shopItemsCount = rawValue(debugBlock, "shop_items_count");
        String unaffordableCount = rawValue(debugBlock, "unaffordable_shop_items_count");
        String preferredArchetype = stringValue(debugBlock, "preferred_archetype");
        String latency = rawValue(debugBlock, "latency_ms");
        String summary = "scene=" + sceneType + " skill=" + selectedSkill + " query=" + queryType + " options=" + optionsCount + " latency=" + latency + "ms";
        if (!shopItemsCount.isEmpty() || !unaffordableCount.isEmpty()) {
            summary += " shop=" + shopItemsCount + " unaff=" + unaffordableCount;
        }
        if (!preferredArchetype.isEmpty()) {
            summary += " target=" + preferredArchetype;
        }
        return summary;
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
        List<String> objects = objectsInArray(json, key);
        return objects.isEmpty() ? "" : objects.get(0);
    }

    private static List<String> objectsInArray(String json, String key) {
        List<String> objects = new ArrayList<String>();
        int keyIndex = json.indexOf("\"" + key + "\"");
        if (keyIndex < 0) {
            return objects;
        }
        int arrayStart = json.indexOf("[", keyIndex);
        if (arrayStart < 0) {
            return objects;
        }
        int arrayEnd = matching(json, arrayStart, '[', ']');
        if (arrayEnd < 0) {
            return objects;
        }
        int cursor = arrayStart + 1;
        while (cursor < arrayEnd) {
            int objectStart = json.indexOf("{", cursor);
            if (objectStart < 0 || objectStart >= arrayEnd) {
                break;
            }
            int objectEnd = matching(json, objectStart, '{', '}');
            if (objectEnd < 0 || objectEnd > arrayEnd) {
                break;
            }
            objects.add(json.substring(objectStart, objectEnd + 1));
            cursor = objectEnd + 1;
        }
        return objects;
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

    private static boolean booleanValue(String json, String key, boolean fallback) {
        String value = rawValue(json, key);
        if (value.isEmpty()) {
            return fallback;
        }
        return "true".equalsIgnoreCase(value);
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
                    case 'u':
                        if (i + 4 < value.length()) {
                            String hex = value.substring(i + 1, i + 5);
                            try {
                                out.append((char) Integer.parseInt(hex, 16));
                                i += 4;
                            } catch (NumberFormatException ex) {
                                out.append("\\u").append(hex);
                                i += 4;
                            }
                        } else {
                            out.append("\\u");
                        }
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
