package com.shadowlink.business.mode.controller;

import com.shadowlink.business.mode.dto.WorkModeCreateRequest;
import com.shadowlink.business.mode.dto.WorkModeUpdateRequest;
import com.shadowlink.business.mode.dto.WorkModeVO;
import com.shadowlink.business.mode.service.WorkModeService;
import com.shadowlink.common.result.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "WorkMode", description = "Ambient work mode management")
@RestController
@RequestMapping("/api/modes")
@RequiredArgsConstructor
public class WorkModeController {

    private final WorkModeService workModeService;

    @Operation(summary = "List all work modes")
    @GetMapping
    public Result<List<WorkModeVO>> list() {
        return Result.ok(workModeService.listAll());
    }

    @Operation(summary = "Get a work mode by ID")
    @GetMapping("/{modeId}")
    public Result<WorkModeVO> get(@PathVariable String modeId) {
        return Result.ok(workModeService.getByModeId(modeId));
    }

    @Operation(summary = "Create a new work mode")
    @PostMapping
    public Result<WorkModeVO> create(@Valid @RequestBody WorkModeCreateRequest request) {
        return Result.ok(workModeService.create(request));
    }

    @Operation(summary = "Update a work mode")
    @PutMapping("/{modeId}")
    public Result<WorkModeVO> update(@PathVariable String modeId,
                                     @Valid @RequestBody WorkModeUpdateRequest request) {
        return Result.ok(workModeService.update(modeId, request));
    }

    @Operation(summary = "Delete a work mode (built-in modes cannot be deleted)")
    @DeleteMapping("/{modeId}")
    public Result<Void> delete(@PathVariable String modeId) {
        workModeService.delete(modeId);
        return Result.ok();
    }
}
