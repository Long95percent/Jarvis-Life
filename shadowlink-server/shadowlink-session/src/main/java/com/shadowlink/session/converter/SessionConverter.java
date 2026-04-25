package com.shadowlink.session.converter;

import com.shadowlink.session.dto.MessageVO;
import com.shadowlink.session.dto.SessionVO;
import com.shadowlink.session.entity.ChatMessage;
import com.shadowlink.session.entity.ChatSession;
import org.mapstruct.Mapper;
import org.mapstruct.factory.Mappers;

import java.util.List;

@Mapper(componentModel = "spring")
public interface SessionConverter {

    SessionConverter INSTANCE = Mappers.getMapper(SessionConverter.class);

    SessionVO toVO(ChatSession entity);

    List<SessionVO> toVOList(List<ChatSession> entities);

    MessageVO toMessageVO(ChatMessage entity);

    List<MessageVO> toMessageVOList(List<ChatMessage> entities);
}
