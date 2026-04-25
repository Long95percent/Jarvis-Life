package com.shadowlink.bridge.service.impl;

import com.shadowlink.bridge.config.AiBridgeProperties;
import com.shadowlink.bridge.service.RagBridgeService;
import com.shadowlink.common.result.Result;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

/**
 * Delegates RAG requests to the Python AI service via REST.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RagBridgeServiceImpl implements RagBridgeService {

    @Qualifier("aiWebClient")
    private final WebClient webClient;
    private final AiBridgeProperties properties;

    @Override
    public Result<Map<String, Object>> query(String query, String modeId, int topK) {
        log.info("RAG query: mode={}, topK={}", modeId, topK);

        Map<String, Object> requestBody = Map.of(
                "query", query,
                "mode_id", modeId,
                "top_k", topK
        );

        @SuppressWarnings("unchecked")
        Map<String, Object> response = webClient.post()
                .uri("/v1/rag/query")
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(Map.class)
                .block();

        return Result.ok(response);
    }

    @Override
    public Result<Map<String, Object>> ingest(String filePath, String modeId) {
        log.info("RAG ingest: file={}, mode={}", filePath, modeId);

        Map<String, Object> requestBody = Map.of(
                "file_path", filePath,
                "mode_id", modeId
        );

        @SuppressWarnings("unchecked")
        Map<String, Object> response = webClient.post()
                .uri("/v1/rag/ingest")
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(Map.class)
                .block();

        return Result.ok(response);
    }
}
