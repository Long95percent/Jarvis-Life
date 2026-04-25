package com.shadowlink.bridge.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

/**
 * WebClient bean for REST fallback to Python AI service.
 */
@Configuration
@RequiredArgsConstructor
public class WebClientConfig {

    private final AiBridgeProperties properties;

    @Bean("aiWebClient")
    public WebClient aiWebClient() {
        return WebClient.builder()
                .baseUrl(properties.getRestBaseUrl())
                .build();
    }
}
