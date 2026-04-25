package com.shadowlink.session.dto;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class MessageVO {

    private Long id;
    private String sessionId;
    private String role;
    private String content;
    private Integer tokenCount;
    private String model;
    private LocalDateTime createdAt;
}
