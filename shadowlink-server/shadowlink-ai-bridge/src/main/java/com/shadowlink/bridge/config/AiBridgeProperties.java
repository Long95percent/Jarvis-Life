package com.shadowlink.bridge.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * Configuration for the Python AI service connection.
 */
@Data
@Component
@ConfigurationProperties(prefix = "shadowlink.ai-service")
public class AiBridgeProperties {

    /** gRPC target address (host:port). */
    private String grpcTarget = "localhost:50051";

    /** REST base URL for HTTP fallback. */
    private String restBaseUrl = "http://localhost:8000";

    /** Timeout in seconds for agent execution. */
    private int timeoutSeconds = 120;

    /** Whether to prefer gRPC over REST. */
    private boolean preferGrpc = true;
}
