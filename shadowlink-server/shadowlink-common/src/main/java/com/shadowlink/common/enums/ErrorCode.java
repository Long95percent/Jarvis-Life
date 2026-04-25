package com.shadowlink.common.enums;

import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * Application-wide error codes.
 * Ranges: 1xxx=auth, 2xxx=validation, 3xxx=business, 4xxx=AI-bridge, 5xxx=system.
 */
@Getter
@AllArgsConstructor
public enum ErrorCode {

    // ── Auth (1xxx) ──
    UNAUTHORIZED(1001, "Not authenticated"),
    FORBIDDEN(1002, "Insufficient permissions"),
    TOKEN_EXPIRED(1003, "Token has expired"),
    TOKEN_INVALID(1004, "Invalid token"),
    LOGIN_FAILED(1005, "Incorrect username or password"),

    // ── Validation (2xxx) ──
    PARAM_INVALID(2001, "Invalid request parameter"),
    PARAM_MISSING(2002, "Required parameter is missing"),

    // ── Business (3xxx) ──
    SESSION_NOT_FOUND(3001, "Chat session not found"),
    MODE_NOT_FOUND(3002, "Work mode not found"),
    MODE_NAME_DUPLICATE(3003, "Work mode name already exists"),
    FILE_UPLOAD_FAILED(3004, "File upload failed"),
    KNOWLEDGE_INDEX_FAILED(3005, "Knowledge base indexing failed"),

    // ── AI Bridge (4xxx) ──
    AI_SERVICE_UNAVAILABLE(4001, "Python AI service is unavailable"),
    AI_EXECUTION_TIMEOUT(4002, "Agent execution timed out"),
    AI_EXECUTION_FAILED(4003, "Agent execution failed"),
    RAG_QUERY_FAILED(4004, "RAG query failed"),

    // ── System (5xxx) ──
    INTERNAL_ERROR(5001, "Internal server error"),
    RATE_LIMIT_EXCEEDED(5002, "Rate limit exceeded, please try again later"),
    SERVICE_DEGRADED(5003, "Service temporarily degraded");

    private final int code;
    private final String message;
}
