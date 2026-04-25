package com.shadowlink.websocket.message;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * Generic WebSocket message envelope.
 * <p>
 * Event types: agent.token, agent.thought, agent.tool_call, agent.tool_result,
 * agent.plan, agent.status, agent.done, agent.error,
 * rag.progress, mode.switch, system.heartbeat.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class WsMessage {

    private String eventType;
    private String sessionId;
    private String content;
    private String toolName;
    private String stepId;
    private Integer tokenCount;
    private Double latencyMs;
    private long timestamp;

    public static WsMessage token(String sessionId, String content) {
        return WsMessage.builder()
                .eventType("agent.token")
                .sessionId(sessionId)
                .content(content)
                .timestamp(System.currentTimeMillis())
                .build();
    }

    public static WsMessage done(String sessionId) {
        return WsMessage.builder()
                .eventType("agent.done")
                .sessionId(sessionId)
                .timestamp(System.currentTimeMillis())
                .build();
    }

    public static WsMessage error(String sessionId, String message) {
        return WsMessage.builder()
                .eventType("agent.error")
                .sessionId(sessionId)
                .content(message)
                .timestamp(System.currentTimeMillis())
                .build();
    }
}
