package com.shadowlink.business.mode.entity;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import com.shadowlink.common.entity.BaseEntity;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.Map;

@Data
@EqualsAndHashCode(callSuper = true)
@TableName(value = "work_mode", autoResultMap = true)
public class WorkMode extends BaseEntity {

    private String modeId;
    private String name;
    private String description;
    private String icon;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> themeConfig;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> agentConfig;

    private String systemPrompt;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Map<String, Object> toolsConfig;

    private Integer sortOrder;
    private Integer isBuiltin;
}
