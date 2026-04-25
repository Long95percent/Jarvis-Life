package com.shadowlink.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.shadowlink.session.entity.ChatSession;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ChatSessionMapper extends BaseMapper<ChatSession> {
}
