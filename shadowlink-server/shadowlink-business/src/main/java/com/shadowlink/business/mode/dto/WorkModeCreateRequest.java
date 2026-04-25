package com.shadowlink.business.mode.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

@Data
public class WorkModeCreateRequest {

    @NotBlank(message = "Mode ID is required")
    @Size(max = 64, message = "Mode ID must be <= 64 chars")
    private String modeId;

    @NotBlank(message = "Name is required")
    @Size(max = 128, message = "Name must be <= 128 chars")
    private String name;

    private String description;
    private String icon;
    private Map<String, Object> themeConfig;
    private Map<String, Object> agentConfig;
    private String systemPrompt;
    private Map<String, Object> toolsConfig;
    private Integer sortOrder;
}
