package com.shadowlink.gateway.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Jarvis proxy — transparent pass-through from Java Gateway to Python AI.
 *
 * <p>All {@code /api/v1/jarvis/*} requests are authenticated (via WHITE_LIST
 * for the L1 demo), logged, and forwarded to the Python service at
 * {@code localhost:8000}. SSE streams are relayed via {@link SseEmitter} so
 * the browser sees a continuous event stream terminated by Python, not Java.</p>
 *
 * <p>Follows the same pattern as {@link ChatProxyController}: servlet-style
 * MVC controller that wraps a reactive {@link WebClient} — REST paths call
 * {@code .block()}, SSE paths subscribe and forward events.</p>
 */
@Slf4j
@Tag(name = "Jarvis Proxy", description = "Transparent proxy to Python Jarvis endpoints")
@RestController
@RequestMapping("/api/v1/jarvis")
@RequiredArgsConstructor
public class JarvisProxyController {

    @Qualifier("aiWebClient")
    private final WebClient webClient;

    private static final long SSE_TIMEOUT = 600_000L; // 10 minutes

    // ── REST catch-all (SSE paths have more specific mappings and take precedence) ─
    @Operation(summary = "Proxy any REST Jarvis request to Python")
    @RequestMapping(
            value = "/**",
            method = {
                    RequestMethod.GET,
                    RequestMethod.POST,
                    RequestMethod.PATCH,
                    RequestMethod.PUT,
                    RequestMethod.DELETE
            }
    )
    public ResponseEntity<byte[]> proxyRest(
            HttpServletRequest request,
            @RequestBody(required = false) byte[] body) {

        String path = request.getRequestURI();             // e.g. /api/v1/jarvis/context
        String query = request.getQueryString();
        String upstream = path + (query != null ? "?" + query : "");
        HttpMethod method = HttpMethod.valueOf(request.getMethod());

        log.debug("Jarvis REST proxy: {} {} (body {} bytes)",
                method, upstream, body == null ? 0 : body.length);

        WebClient.RequestBodySpec spec = webClient.method(method).uri(upstream);
        if (body != null && body.length > 0) {
            spec.contentType(MediaType.APPLICATION_JSON).bodyValue(body);
        }

        try {
            return spec.retrieve()
                    .toEntity(byte[].class)
                    .block();
        } catch (WebClientResponseException e) {
            return ResponseEntity
                    .status(e.getStatusCode())
                    .contentType(e.getHeaders().getContentType() != null
                            ? e.getHeaders().getContentType()
                            : MediaType.APPLICATION_JSON)
                    .header("X-Request-ID", e.getHeaders().getFirst("X-Request-ID"))
                    .body(e.getResponseBodyAsByteArray());
        } catch (WebClientRequestException e) {
            log.warn("Jarvis REST proxy could not reach Python AI service: {} {} -> {}",
                    method, upstream, e.getMessage());
            return ResponseEntity
                    .status(HttpStatus.SERVICE_UNAVAILABLE)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(aiServiceUnavailableBody(e).getBytes(StandardCharsets.UTF_8));
        }
    }

    // ── SSE: proactive messages stream (GET) ──────────────────────────────────
    @Operation(summary = "SSE stream of proactive messages from agents")
    @GetMapping(value = "/messages/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamMessages() {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT);

        log.info("Jarvis SSE proxy: GET /api/v1/jarvis/messages/stream");

        webClient.get()
                .uri("/api/v1/jarvis/messages/stream")
                .accept(MediaType.TEXT_EVENT_STREAM)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {})
                .subscribe(
                        sse -> forwardSse(emitter, sse),
                        error -> failSse(emitter, error),
                        emitter::complete
                );

        emitter.onTimeout(() -> log.warn("Jarvis SSE /messages/stream timed out"));
        emitter.onCompletion(() -> log.debug("Jarvis SSE /messages/stream closed"));
        return emitter;
    }

    // ── SSE: roundtable start (POST) ──────────────────────────────────────────
    @Operation(summary = "Start a scenario roundtable, SSE stream")
    @PostMapping(value = "/roundtable/start", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter roundtableStart(@RequestBody String rawBody) {
        return forwardPostSse("/api/v1/jarvis/roundtable/start", rawBody);
    }

    // ── SSE: roundtable continue (POST) ───────────────────────────────────────
    @Operation(summary = "Continue an ongoing roundtable with a user message, SSE stream")
    @PostMapping(value = "/roundtable/continue", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter roundtableContinue(@RequestBody String rawBody) {
        return forwardPostSse("/api/v1/jarvis/roundtable/continue", rawBody);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private SseEmitter forwardPostSse(String uri, String rawBody) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT);

        log.info("Jarvis SSE proxy: POST {}", uri);

        webClient.post()
                .uri(uri)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .bodyValue(rawBody == null ? "" : rawBody)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {})
                .subscribe(
                        sse -> forwardSse(emitter, sse),
                        error -> failSse(emitter, error),
                        emitter::complete
                );

        emitter.onTimeout(() -> log.warn("Jarvis SSE {} timed out", uri));
        emitter.onCompletion(() -> log.debug("Jarvis SSE {} closed", uri));
        return emitter;
    }

    private void forwardSse(SseEmitter emitter, ServerSentEvent<String> sse) {
        try {
            SseEmitter.SseEventBuilder builder = SseEmitter.event();
            if (sse.event() != null) {
                builder.name(sse.event());
            }
            if (sse.id() != null) {
                builder.id(sse.id());
            }
            if (sse.data() != null) {
                builder.data(sse.data());
            }
            emitter.send(builder);
        } catch (IOException e) {
            log.warn("Jarvis SSE send failed (client likely disconnected): {}", e.getMessage());
            emitter.completeWithError(e);
        }
    }

    private void failSse(SseEmitter emitter, Throwable error) {
        log.error("Jarvis SSE upstream error: ", error);
        try {
            String msg = error.getMessage() != null
                    ? error.getMessage().replace("\"", "\\\"").replace("\n", "\\n")
                    : "Unknown Error";
            emitter.send(SseEmitter.event()
                    .name("error")
                    .data("{\"event\":\"error\",\"data\":{\"content\":\"" + msg + "\"}}"));
        } catch (IOException ignored) {
            // Client already gone
        }
        emitter.completeWithError(error);
    }

    private String aiServiceUnavailableBody(WebClientRequestException e) {
        String message = escapeJson(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage());
        return "{"
                + "\"success\":false,"
                + "\"code\":503,"
                + "\"message\":\"Python AI service is unavailable\","
                + "\"data\":{"
                + "\"error_type\":\"" + e.getClass().getSimpleName() + "\","
                + "\"error\":\"" + message + "\","
                + "\"suggestion\":\"请确认 shadowlink-ai 服务已启动，且 shadowlink.ai-service.rest-base-url 指向正确的 Python AI 地址。\""
                + "}"
                + "}";
    }

    private String escapeJson(String value) {
        return value
                .replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\r", "\\r")
                .replace("\n", "\\n");
    }
}
