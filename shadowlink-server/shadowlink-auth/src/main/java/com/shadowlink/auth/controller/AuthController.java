package com.shadowlink.auth.controller;

import com.shadowlink.auth.dto.LoginRequest;
import com.shadowlink.auth.dto.LoginResponse;
import com.shadowlink.auth.dto.RefreshRequest;
import com.shadowlink.auth.service.AuthService;
import com.shadowlink.common.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Auth", description = "Authentication and token management")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @Operation(summary = "Login — returns JWT access + refresh tokens")
    @PostMapping("/login")
    public Result<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return Result.ok(authService.login(request));
    }

    @Operation(summary = "Refresh — exchange refresh token for new access token")
    @PostMapping("/refresh")
    public Result<LoginResponse> refresh(@Valid @RequestBody RefreshRequest request) {
        return Result.ok(authService.refresh(request));
    }

    @Operation(summary = "Logout — invalidate the current token")
    @PostMapping("/logout")
    public Result<Void> logout(@RequestHeader("Authorization") String token) {
        authService.logout(token);
        return Result.ok();
    }
}
