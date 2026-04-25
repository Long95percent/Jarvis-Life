package com.shadowlink.business.mode.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
public class WorkModeVO {

    private String modeId;
    private String name;
    private String description;
    private String icon;
    private Map<String, Object> themeConfig;
    private Map<String, Object> agentConfig;
    private String systemPrompt;
    private Map<String, Object> toolsConfig;
    private Integer sortOrder;
    private Integer isBuiltin;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
