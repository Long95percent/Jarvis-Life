package com.shadowlink.session.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import com.shadowlink.common.entity.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName("chat_session")
public class ChatSession extends BaseEntity {

    private String sessionId;
    private String modeId;
    private String title;
}
