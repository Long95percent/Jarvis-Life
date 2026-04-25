package com.shadowlink.bridge.service;

import com.shadowlink.common.result.Result;

import java.util.Map;

/**
 * Bridge to the Python RAG service.
 */
public interface RagBridgeService {

    /**
     * Execute RAG query via Python service.
     * Phase 0: placeholder.
     */
    Result<Map<String, Object>> query(String query, String modeId, int topK);

    /**
     * Trigger document ingestion.
     * Phase 0: placeholder.
     */
    Result<Map<String, Object>> ingest(String filePath, String modeId);
}
