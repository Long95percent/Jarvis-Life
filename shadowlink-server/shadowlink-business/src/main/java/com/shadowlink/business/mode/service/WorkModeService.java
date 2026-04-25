package com.shadowlink.business.mode.service;

import com.shadowlink.business.mode.dto.WorkModeCreateRequest;
import com.shadowlink.business.mode.dto.WorkModeUpdateRequest;
import com.shadowlink.business.mode.dto.WorkModeVO;

import java.util.List;

public interface WorkModeService {

    List<WorkModeVO> listAll();

    WorkModeVO getByModeId(String modeId);

    WorkModeVO create(WorkModeCreateRequest request);

    WorkModeVO update(String modeId, WorkModeUpdateRequest request);

    void delete(String modeId);
}
