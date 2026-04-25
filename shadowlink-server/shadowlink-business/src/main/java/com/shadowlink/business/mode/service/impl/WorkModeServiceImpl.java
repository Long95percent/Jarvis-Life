package com.shadowlink.business.mode.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.shadowlink.business.mode.converter.WorkModeConverter;
import com.shadowlink.business.mode.dto.WorkModeCreateRequest;
import com.shadowlink.business.mode.dto.WorkModeUpdateRequest;
import com.shadowlink.business.mode.dto.WorkModeVO;
import com.shadowlink.business.mode.entity.WorkMode;
import com.shadowlink.business.mode.mapper.WorkModeMapper;
import com.shadowlink.business.mode.service.WorkModeService;
import com.shadowlink.common.enums.ErrorCode;
import com.shadowlink.common.exception.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class WorkModeServiceImpl implements WorkModeService {

    private final WorkModeMapper modeMapper;
    private final WorkModeConverter converter;

    @Override
    public List<WorkModeVO> listAll() {
        LambdaQueryWrapper<WorkMode> wrapper = new LambdaQueryWrapper<WorkMode>()
                .orderByAsc(WorkMode::getSortOrder)
                .orderByAsc(WorkMode::getCreatedAt);
        return converter.toVOList(modeMapper.selectList(wrapper));
    }

    @Override
    public WorkModeVO getByModeId(String modeId) {
        return converter.toVO(findByModeId(modeId));
    }

    @Override
    @Transactional
    public WorkModeVO create(WorkModeCreateRequest request) {
        // Check duplicate
        WorkMode existing = modeMapper.selectOne(
                new LambdaQueryWrapper<WorkMode>()
                        .eq(WorkMode::getModeId, request.getModeId()));
        if (existing != null) {
            throw new BizException(ErrorCode.MODE_NAME_DUPLICATE);
        }

        WorkMode entity = converter.toEntity(request);
        entity.setIsBuiltin(0);
        modeMapper.insert(entity);
        return converter.toVO(entity);
    }

    @Override
    @Transactional
    public WorkModeVO update(String modeId, WorkModeUpdateRequest request) {
        WorkMode entity = findByModeId(modeId);

        if (request.getName() != null) entity.setName(request.getName());
        if (request.getDescription() != null) entity.setDescription(request.getDescription());
        if (request.getIcon() != null) entity.setIcon(request.getIcon());
        if (request.getThemeConfig() != null) entity.setThemeConfig(request.getThemeConfig());
        if (request.getAgentConfig() != null) entity.setAgentConfig(request.getAgentConfig());
        if (request.getSystemPrompt() != null) entity.setSystemPrompt(request.getSystemPrompt());
        if (request.getToolsConfig() != null) entity.setToolsConfig(request.getToolsConfig());
        if (request.getSortOrder() != null) entity.setSortOrder(request.getSortOrder());

        modeMapper.updateById(entity);
        return converter.toVO(entity);
    }

    @Override
    @Transactional
    public void delete(String modeId) {
        WorkMode entity = findByModeId(modeId);
        if (entity.getIsBuiltin() != null && entity.getIsBuiltin() == 1) {
            throw new BizException(3006, "Cannot delete built-in work mode");
        }
        modeMapper.deleteById(entity.getId());
    }

    private WorkMode findByModeId(String modeId) {
        WorkMode entity = modeMapper.selectOne(
                new LambdaQueryWrapper<WorkMode>()
                        .eq(WorkMode::getModeId, modeId));
        if (entity == null) {
            throw new BizException(ErrorCode.MODE_NOT_FOUND);
        }
        return entity;
    }
}
