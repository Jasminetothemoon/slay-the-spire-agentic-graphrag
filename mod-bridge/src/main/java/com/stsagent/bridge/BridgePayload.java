package com.stsagent.bridge;

import java.util.Collections;
import java.util.List;

public class BridgePayload {
    private final String stateJson;
    private final String queryType;
    private final List<String> options;
    private final String userQuery;

    public BridgePayload(String stateJson, String queryType, List<String> options, String userQuery) {
        this.stateJson = stateJson;
        this.queryType = queryType;
        this.options = options == null ? Collections.<String>emptyList() : options;
        this.userQuery = userQuery == null ? "" : userQuery;
    }

    public String stateJson() {
        return stateJson;
    }

    public String queryType() {
        return queryType;
    }

    public List<String> options() {
        return options;
    }

    public String userQuery() {
        return userQuery;
    }

    public boolean hasDecision() {
        return queryType != null && !queryType.isEmpty() && !options.isEmpty();
    }

    public String signature() {
        return stateJson + "|" + queryType + "|" + options.toString();
    }
}
