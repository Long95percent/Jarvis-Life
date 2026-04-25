package com.shadowlink.websocket.handler;

import com.shadowlink.websocket.message.WsMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;

/**
 * Handles inbound STOMP messages from clients and dispatches to AI bridge.
 */
@Slf4j
@Controller
@RequiredArgsConstructor
public class ChatMessageHandler {

    private final SimpMessagingTemplate messagingTemplate;

    /**
     * Client sends a chat message → dispatches to Agent bridge (Phase 1+).
     * For now, echoes back a placeholder response.
     */
    @MessageMapping("/chat.send/{sessionId}")
    public void handleChat(@DestinationVariable String sessionId, WsMessage inbound) {
        log.info("WS message received for session {}: {}", sessionId, inbound.getContent());
        // Phase 1: call AIBridgeService.streamExecute() and push events
        // For skeleton validation, send an echo response:
        WsMessage response = WsMessage.token(sessionId,
                "[echo] " + inbound.getContent());
        messagingTemplate.convertAndSend("/topic/session/" + sessionId, response);
        messagingTemplate.convertAndSend("/topic/session/" + sessionId,
                WsMessage.done(sessionId));
    }

    /** Push a message to a specific session topic (called from AI bridge). */
    public void pushToSession(String sessionId, WsMessage message) {
        messagingTemplate.convertAndSend("/topic/session/" + sessionId, message);
    }
}
