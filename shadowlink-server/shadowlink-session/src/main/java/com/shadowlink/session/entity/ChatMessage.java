package com.shadowlink.session.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@TableName("chat_message")
public class ChatMessage implements Serializable {

    @TableId(type = IdType.ASSIGN_ID)
    private Long id;
    private String sessionId;
    private String role;
    private String content;
    private Integer tokenCount;
    private String model;
    private LocalDateTime createdAt;
}
