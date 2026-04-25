package com.shadowlink.session.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.shadowlink.session.entity.ChatMessage;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ChatMessageMapper extends BaseMapper<ChatMessage> {
}
