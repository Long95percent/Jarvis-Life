package com.shadowlink.business.mode.dto;

import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

@Data
public class WorkModeUpdateRequest {

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
