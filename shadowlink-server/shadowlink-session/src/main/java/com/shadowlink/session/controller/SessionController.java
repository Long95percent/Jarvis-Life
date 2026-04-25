package com.shadowlink.session.controller;

import com.shadowlink.common.result.Result;
import com.shadowlink.session.dto.MessageVO;
import com.shadowlink.session.dto.SessionCreateRequest;
import com.shadowlink.session.dto.SessionVO;
import com.shadowlink.session.service.SessionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "Session", description = "Chat session lifecycle management")
@RestController
@RequestMapping("/api/sessions")
@RequiredArgsConstructor
public class SessionController {

    private final SessionService sessionService;

    @Operation(summary = "Create a new chat session")
    @PostMapping
    public Result<SessionVO> create(@Valid @RequestBody SessionCreateRequest request) {
        return Result.ok(sessionService.createSession(request));
    }

    @Operation(summary = "List sessions, optionally filtered by mode")
    @GetMapping
    public Result<List<SessionVO>> list(@RequestParam(required = false) String modeId) {
        return Result.ok(sessionService.listSessions(modeId));
    }

    @Operation(summary = "Get session detail")
    @GetMapping("/{sessionId}")
    public Result<SessionVO> get(@PathVariable String sessionId) {
        return Result.ok(sessionService.getSession(sessionId));
    }

    @Operation(summary = "Delete a session and all its messages")
    @DeleteMapping("/{sessionId}")
    public Result<Void> delete(@PathVariable String sessionId) {
        sessionService.deleteSession(sessionId);
        return Result.ok();
    }

    @Operation(summary = "Rename a session")
    @PatchMapping("/{sessionId}/title")
    public Result<Void> rename(@PathVariable String sessionId, @RequestParam String title) {
        sessionService.renameSession(sessionId, title);
        return Result.ok();
    }

    @Operation(summary = "Get all messages in a session")
    @GetMapping("/{sessionId}/messages")
    public Result<List<MessageVO>> messages(@PathVariable String sessionId) {
        return Result.ok(sessionService.getMessages(sessionId));
    }
}
