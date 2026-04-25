package com.shadowlink.auth.service.impl;

import com.shadowlink.auth.config.JwtProperties;
import com.shadowlink.auth.dto.LoginRequest;
import com.shadowlink.auth.dto.LoginResponse;
import com.shadowlink.auth.dto.RefreshRequest;
import com.shadowlink.auth.service.AuthService;
import com.shadowlink.auth.service.JwtService;
import com.shadowlink.common.enums.ErrorCode;
import com.shadowlink.common.exception.BizException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.AuthenticationException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Authentication service implementation.
 * Phase 0: Uses a hard-coded demo user for skeleton validation.
 * Phase 1+: Will integrate with UserMapper + database-backed user store.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final JwtService jwtService;
    private final JwtProperties jwtProperties;
    private final AuthenticationManager authenticationManager;

    @Override
    public LoginResponse login(LoginRequest request) {
        try {
            authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(
                            request.getUsername(), request.getPassword()));
        } catch (AuthenticationException e) {
            throw new BizException(ErrorCode.LOGIN_FAILED);
        }

        List<String> roles = List.of("ROLE_USER");
        String accessToken = jwtService.generateAccessToken(request.getUsername(), roles);
        String refreshToken = jwtService.generateRefreshToken(request.getUsername());

        return LoginResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .expiresIn(jwtProperties.getAccessTokenExpireMinutes() * 60)
                .username(request.getUsername())
                .build();
    }

    @Override
    public LoginResponse refresh(RefreshRequest request) {
        String token = request.getRefreshToken();
        if (!jwtService.isTokenValid(token)) {
            throw new BizException(ErrorCode.TOKEN_EXPIRED);
        }

        String username = jwtService.extractUsername(token);
        List<String> roles = List.of("ROLE_USER");
        String newAccessToken = jwtService.generateAccessToken(username, roles);
        String newRefreshToken = jwtService.generateRefreshToken(username);

        return LoginResponse.builder()
                .accessToken(newAccessToken)
                .refreshToken(newRefreshToken)
                .expiresIn(jwtProperties.getAccessTokenExpireMinutes() * 60)
                .username(username)
                .build();
    }

    @Override
    public void logout(String token) {
        // Phase 1+: Add token to Redis blacklist
        log.info("User logged out, token invalidated (blacklist pending Redis integration)");
    }
}
