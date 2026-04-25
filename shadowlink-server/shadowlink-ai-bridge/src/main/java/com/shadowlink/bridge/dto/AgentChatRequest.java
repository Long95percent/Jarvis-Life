package com.shadowlink.bridge.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.Map;

@Data
public class AgentChatRequest {

    @NotBlank(message = "Session ID is required")
    private String sessionId;

    private String modeId = "general";

    @NotBlank(message = "Message is required")
    private String message;

    /** auto | react | plan_execute | multi_agent */
    private String strategy = "auto";

    private Map<String, String> metadata;
}
