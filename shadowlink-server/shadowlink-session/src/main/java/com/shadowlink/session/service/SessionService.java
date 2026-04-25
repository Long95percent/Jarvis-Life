package com.shadowlink.session.service;

import com.shadowlink.session.dto.MessageVO;
import com.shadowlink.session.dto.SessionCreateRequest;
import com.shadowlink.session.dto.SessionVO;

import java.util.List;

public interface SessionService {

    SessionVO createSession(SessionCreateRequest request);

    List<SessionVO> listSessions(String modeId);

    SessionVO getSession(String sessionId);

    void deleteSession(String sessionId);

    void renameSession(String sessionId, String title);

    List<MessageVO> getMessages(String sessionId);
}
