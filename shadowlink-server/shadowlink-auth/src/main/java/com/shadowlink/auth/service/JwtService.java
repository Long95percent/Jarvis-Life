package com.shadowlink.auth.service;

import com.shadowlink.auth.config.JwtProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;

/**
 * JWT token generation and validation service.
 */
@Service
@RequiredArgsConstructor
public class JwtService {

    private final JwtProperties jwtProperties;

    /** Generate an access token for the given user. */
    public String generateAccessToken(String username, List<String> roles) {
        return buildToken(username, roles,
                Duration.ofMinutes(jwtProperties.getAccessTokenExpireMinutes()));
    }

    /** Generate a refresh token (longer-lived, minimal claims). */
    public String generateRefreshToken(String username) {
        return buildToken(username, Collections.emptyList(),
                Duration.ofDays(jwtProperties.getRefreshTokenExpireDays()));
    }

    public String extractUsername(String token) {
        return parseClaims(token).getSubject();
    }

    @SuppressWarnings("unchecked")
    public List<String> extractRoles(String token) {
        Object roles = parseClaims(token).get("roles");
        if (roles instanceof List<?> list) {
            return (List<String>) list;
        }
        return Collections.emptyList();
    }

    public boolean isTokenValid(String token) {
        try {
            Claims claims = parseClaims(token);
            return claims.getExpiration().after(new Date());
        } catch (Exception e) {
            return false;
        }
    }

    // ── Internal ──

    private String buildToken(String username, List<String> roles, Duration expiry) {
        Date now = new Date();
        Date expiration = new Date(now.getTime() + expiry.toMillis());

        return Jwts.builder()
                .subject(username)
                .issuer(jwtProperties.getIssuer())
                .issuedAt(now)
                .expiration(expiration)
                .claim("roles", roles)
                .signWith(getSigningKey())
                .compact();
    }

    private Claims parseClaims(String token) {
        return Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    private SecretKey getSigningKey() {
        byte[] keyBytes = jwtProperties.getSecret().getBytes(StandardCharsets.UTF_8);
        return Keys.hmacShaKeyFor(keyBytes);
    }
}
