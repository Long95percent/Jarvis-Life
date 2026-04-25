package com.shadowlink.common.exception;

import com.shadowlink.common.enums.ErrorCode;
import lombok.Getter;

/**
 * Business logic exception — carries an {@link ErrorCode} for structured error responses.
 */
@Getter
public class BizException extends RuntimeException {

    private final int code;

    public BizException(int code, String message) {
        super(message);
        this.code = code;
    }

    public BizException(String message) {
        this(500, message);
    }

    public BizException(ErrorCode errorCode) {
        this(errorCode.getCode(), errorCode.getMessage());
    }

    public BizException(ErrorCode errorCode, String detail) {
        this(errorCode.getCode(), errorCode.getMessage() + ": " + detail);
    }
}
