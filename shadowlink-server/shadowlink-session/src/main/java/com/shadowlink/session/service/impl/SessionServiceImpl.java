package com.shadowlink.session.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.shadowlink.common.enums.ErrorCode;
import com.shadowlink.common.exception.BizException;
import com.shadowlink.common.util.IdGenerator;
import com.shadowlink.session.converter.SessionConverter;
import com.shadowlink.session.dto.MessageVO;
import com.shadowlink.session.dto.SessionCreateRequest;
import com.shadowlink.session.dto.SessionVO;
import com.shadowlink.session.entity.ChatMessage;
import com.shadowlink.session.entity.ChatSession;
import com.shadowlink.session.mapper.ChatMessageMapper;
import com.shadowlink.session.mapper.ChatSessionMapper;
import com.shadowlink.session.service.SessionService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class SessionServiceImpl implements SessionService {

    private final ChatSessionMapper sessionMapper;
    private final ChatMessageMapper messageMapper;
    private final SessionConverter converter;

    @Override
    @Transactional
    public SessionVO createSession(SessionCreateRequest request) {
        ChatSession session = new ChatSession();
        session.setSessionId(IdGenerator.prefixed("sess"));
        session.setModeId(request.getModeId());
        session.setTitle(request.getTitle() != null ? request.getTitle() : "New Chat");
        sessionMapper.insert(session);
        return converter.toVO(session);
    }

    @Override
    public List<SessionVO> listSessions(String modeId) {
        LambdaQueryWrapper<ChatSession> wrapper = new LambdaQueryWrapper<ChatSession>()
                .eq(modeId != null, ChatSession::getModeId, modeId)
                .orderByDesc(ChatSession::getUpdatedAt);
        return converter.toVOList(sessionMapper.selectList(wrapper));
    }

    @Override
    public SessionVO getSession(String sessionId) {
        ChatSession session = findBySessionId(sessionId);
        return converter.toVO(session);
    }

    @Override
    @Transactional
    public void deleteSession(String sessionId) {
        ChatSession session = findBySessionId(sessionId);
        sessionMapper.deleteById(session.getId());
        messageMapper.delete(new LambdaQueryWrapper<ChatMessage>()
                .eq(ChatMessage::getSessionId, sessionId));
    }

    @Override
    @Transactional
    public void renameSession(String sessionId, String title) {
        ChatSession session = findBySessionId(sessionId);
        session.setTitle(title);
        sessionMapper.updateById(session);
    }

    @Override
    public List<MessageVO> getMessages(String sessionId) {
        LambdaQueryWrapper<ChatMessage> wrapper = new LambdaQueryWrapper<ChatMessage>()
                .eq(ChatMessage::getSessionId, sessionId)
                .orderByAsc(ChatMessage::getCreatedAt);
        return converter.toMessageVOList(messageMapper.selectList(wrapper));
    }

    private ChatSession findBySessionId(String sessionId) {
        ChatSession session = sessionMapper.selectOne(
                new LambdaQueryWrapper<ChatSession>()
                        .eq(ChatSession::getSessionId, sessionId));
        if (session == null) {
            throw new BizException(ErrorCode.SESSION_NOT_FOUND);
        }
        return session;
    }
}
