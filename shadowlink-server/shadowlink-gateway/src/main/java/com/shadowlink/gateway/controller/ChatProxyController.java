package com.shadowlink.gateway.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;

/**
 * Transparent SSE proxy from frontend to Python AI service.
 *
 * <p>The frontend POSTs to {@code /api/ai/agent/stream} with a JSON body.
 * This controller forwards the raw request body to Python's
 * {@code /v1/agent/chat/stream} endpoint and streams SSE events back
 * without parsing or transforming them.</p>
 */
@Slf4j
@Tag(name = "AI Proxy", description = "Transparent SSE proxy to Python AI service")
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class ChatProxyController {

    @Qualifier("aiWebClient")
    private final WebClient webClient;

    private static final long SSE_TIMEOUT = 600_000L; // 10 minutes

    @Operation(summary = "Stream agent chat via SSE (proxy to Python)")
    @PostMapping(value = "/agent/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamAgent(@RequestBody String rawBody) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT);

        log.info("Received SSE request from frontend, forwarding to Python...");

        webClient.post()
                .uri("/v1/agent/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(rawBody)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {})
                .subscribe(
                        sse -> {
                            try {
                                SseEmitter.SseEventBuilder builder = SseEmitter.event();
                                if (sse.event() != null) {
                                    builder.name(sse.event());
                                }
                                if (sse.data() != null) {
                                    builder.data(sse.data());
                                }
                                emitter.send(builder);
                            } catch (IOException e) {
                                log.warn("SSE send failed (client likely disconnected): {}", e.getMessage());
                                emitter.completeWithError(e);
                            }
                        },
                        error -> {
                            log.error("Python AI stream error: ", error);
                            try {
                                String errorMsg = error.getMessage() != null ? error.getMessage().replace("\"", "\\\"").replace("\n", "\\n") : "Unknown Error";
                                emitter.send(SseEmitter.event()
                                        .name("error")
                                        .data("{\"event\":\"error\",\"data\":{\"content\":\"" + errorMsg + "\"}}"));
                            } catch (IOException ignored) {
                                // Client already gone
                            }
                            emitter.completeWithError(error);
                        },
                        () -> {
                            log.info("Python AI stream completed successfully");
                            emitter.complete();
                        }
                );

        emitter.onTimeout(() -> log.warn("SSE connection timed out"));
        emitter.onCompletion(() -> log.debug("SSE connection closed"));

        return emitter;
    }

    @Operation(summary = "Non-streaming agent chat (proxy to Python)")
    @PostMapping(value = "/agent/chat", produces = MediaType.APPLICATION_JSON_VALUE)
    public String chatAgent(@RequestBody String rawBody) {
        return webClient.post()
                .uri("/v1/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(rawBody)
                .retrieve()
                .bodyToMono(String.class)
                .block();
    }
}
