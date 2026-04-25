package com.shadowlink.session.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class SessionVO {

    private String sessionId;
    private String modeId;
    private String title;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
