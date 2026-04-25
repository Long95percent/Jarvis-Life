package com.shadowlink.session.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class SessionCreateRequest {

    @NotBlank(message = "Mode ID is required")
    private String modeId;

    private String title;
}
