package com.shadowlink.bridge.service.impl;

import com.shadowlink.bridge.client.AiRestClient;
import com.shadowlink.bridge.dto.AgentChatRequest;
import com.shadowlink.bridge.dto.AgentEventDTO;
import com.shadowlink.bridge.service.AgentBridgeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

/**
 * Delegates agent chat requests to the Python AI service via REST.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentBridgeServiceImpl implements AgentBridgeService {

    private final AiRestClient aiRestClient;

    @Override
    public Flux<AgentEventDTO> streamChat(AgentChatRequest request) {
        log.info("Bridge streamChat: session={}, mode={}, strategy={}",
                request.getSessionId(), request.getModeId(), request.getStrategy());
        return aiRestClient.streamChat(request);
    }
}
