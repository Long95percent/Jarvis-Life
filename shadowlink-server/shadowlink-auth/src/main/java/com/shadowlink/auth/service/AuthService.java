package com.shadowlink.auth.service;

import com.shadowlink.auth.dto.LoginRequest;
import com.shadowlink.auth.dto.LoginResponse;
import com.shadowlink.auth.dto.RefreshRequest;

public interface AuthService {

    LoginResponse login(LoginRequest request);

    LoginResponse refresh(RefreshRequest request);

    void logout(String token);
}
