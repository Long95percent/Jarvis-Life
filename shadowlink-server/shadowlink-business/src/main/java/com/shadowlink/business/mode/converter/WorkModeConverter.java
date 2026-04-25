package com.shadowlink.business.mode.converter;

import com.shadowlink.business.mode.dto.WorkModeCreateRequest;
import com.shadowlink.business.mode.dto.WorkModeVO;
import com.shadowlink.business.mode.entity.WorkMode;
import org.mapstruct.Mapper;
import org.mapstruct.factory.Mappers;

import java.util.List;

@Mapper(componentModel = "spring")
public interface WorkModeConverter {

    WorkModeConverter INSTANCE = Mappers.getMapper(WorkModeConverter.class);

    WorkModeVO toVO(WorkMode entity);

    List<WorkModeVO> toVOList(List<WorkMode> entities);

    WorkMode toEntity(WorkModeCreateRequest request);
}
