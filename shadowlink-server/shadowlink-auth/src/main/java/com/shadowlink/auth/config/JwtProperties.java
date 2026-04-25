package com.shadowlink.auth.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * JWT configuration properties — bound to application.yml prefix "shadowlink.jwt".
 */
@Data
@Component
@ConfigurationProperties(prefix = "shadowlink.jwt")
public class JwtProperties {

    private String secret = "shadowlink-default-secret-key-replace-in-production-at-least-256-bits!!";
    private long accessTokenExpireMinutes = 30;
    private long refreshTokenExpireDays = 7;
    private String issuer = "shadowlink";
}
