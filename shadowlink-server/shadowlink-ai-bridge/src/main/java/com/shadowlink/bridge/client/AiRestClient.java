package com.shadowlink.bridge.client;

import com.shadowlink.bridge.config.AiBridgeProperties;
import com.shadowlink.bridge.dto.AgentChatRequest;
import com.shadowlink.bridge.dto.AgentEventDTO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

/**
 * REST client for the Python AI service.
 * Supports both non-streaming and SSE streaming calls.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AiRestClient {

    @Qualifier("aiWebClient")
    private final WebClient webClient;
    private final AiBridgeProperties properties;

    /**
     * Non-streaming agent chat — calls Python /v1/agent/chat.
     */
    public Flux<AgentEventDTO> streamChat(AgentChatRequest request) {
        return webClient.post()
                .uri("/v1/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(AgentEventDTO.class)
                .doOnError(e -> log.error("REST agent call failed: {}", e.getMessage()));
    }

    /**
     * SSE streaming agent chat — calls Python /v1/agent/chat/stream.
     * Returns raw SSE events for transparent proxying.
     */
    public Flux<ServerSentEvent<String>> streamChatSSE(AgentChatRequest request) {
        return webClient.post()
                .uri("/v1/agent/chat/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(request)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {})
                .doOnError(e -> log.error("SSE agent stream failed: {}", e.getMessage()));
    }

    /**
     * Health check — calls Python /health.
     */
    public Mono<String> healthCheck() {
        return webClient.get()
                .uri("/health")
                .retrieve()
                .bodyToMono(String.class)
                .doOnError(e -> log.warn("Python health check failed: {}", e.getMessage()));
    }
}
