package com.shadowlink.common.constant;

/**
 * Application-wide constants.
 */
public final class AppConstants {

    private AppConstants() {}

    // ── Defaults ──
    public static final String DEFAULT_MODE = "general";
    public static final int MAX_SESSION_HISTORY = 100;
    public static final int DEFAULT_PAGE_SIZE = 20;

    // ── AI Bridge ──
    public static final String AI_SERVICE_GRPC_TARGET = "localhost:50051";
    public static final int AI_SERVICE_TIMEOUT_SECONDS = 120;

    // ── JWT ──
    public static final String TOKEN_HEADER = "Authorization";
    public static final String TOKEN_PREFIX = "Bearer ";
    public static final long ACCESS_TOKEN_EXPIRE_MINUTES = 30;
    public static final long REFRESH_TOKEN_EXPIRE_DAYS = 7;

    // ── WebSocket ──
    public static final String WS_ENDPOINT = "/ws/chat";
    public static final String WS_TOPIC_PREFIX = "/topic";
    public static final String WS_APP_PREFIX = "/app";

    // ── Redis Key Prefixes ──
    public static final String REDIS_TOKEN_PREFIX = "sl:token:";
    public static final String REDIS_SESSION_PREFIX = "sl:session:";
    public static final String REDIS_RATE_LIMIT_PREFIX = "sl:rate:";
}
