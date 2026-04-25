package com.shadowlink.bridge.service;

import com.shadowlink.bridge.dto.AgentChatRequest;
import com.shadowlink.bridge.dto.AgentEventDTO;
import reactor.core.publisher.Flux;

/**
 * Bridge to the Python Agent service.
 * Supports both gRPC streaming and REST fallback.
 */
public interface AgentBridgeService {

    /**
     * Stream agent execution events for a chat request.
     * Phase 0: returns a placeholder Flux.
     * Phase 1+: delegates to gRPC AgentService.Chat or REST /v1/agent/chat.
     */
    Flux<AgentEventDTO> streamChat(AgentChatRequest request);
}
