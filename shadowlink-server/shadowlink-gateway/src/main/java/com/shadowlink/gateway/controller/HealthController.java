package com.shadowlink.gateway.controller;

import com.shadowlink.common.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.Map;

@Tag(name = "Health", description = "Service health and readiness checks")
@RestController
public class HealthController {

    @Operation(summary = "Health check")
    @GetMapping("/health")
    public Result<Map<String, Object>> health() {
        return Result.ok(Map.of(
                "status", "UP",
                "service", "shadowlink-server",
                "timestamp", Instant.now().toString()
        ));
    }
}
