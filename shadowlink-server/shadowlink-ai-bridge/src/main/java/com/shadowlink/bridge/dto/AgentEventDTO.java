package com.shadowlink.bridge.dto;

import lombok.Data;

@Data
public class AgentEventDTO {

    private String eventType;
    private String content;
    private String toolName;
    private Integer tokenCount;
    private Double latencyMs;
    private String stepId;
}
