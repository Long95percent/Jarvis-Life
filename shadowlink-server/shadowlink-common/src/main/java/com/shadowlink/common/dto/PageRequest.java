package com.shadowlink.common.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

import java.io.Serializable;

/**
 * Standard pagination request — embed in query DTOs.
 */
@Data
public class PageRequest implements Serializable {

    @Min(value = 1, message = "Page number must be >= 1")
    private int page = 1;

    @Min(value = 1, message = "Page size must be >= 1")
    @Max(value = 100, message = "Page size must be <= 100")
    private int size = 20;

    private String sortBy;
    private boolean asc = true;
}
