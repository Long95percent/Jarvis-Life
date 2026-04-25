package com.shadowlink.common.util;

import cn.hutool.core.util.IdUtil;

/**
 * Centralized ID generation — wraps Hutool snowflake + UUID utilities.
 */
public final class IdGenerator {

    private IdGenerator() {}

    /** Snowflake ID (long, suitable for primary keys). */
    public static long snowflakeId() {
        return IdUtil.getSnowflakeNextId();
    }

    /** Short UUID (32 chars hex, no dashes). */
    public static String uuid() {
        return IdUtil.simpleUUID();
    }

    /** Generate a prefixed business ID, e.g. "sess_abc123..." */
    public static String prefixed(String prefix) {
        return prefix + "_" + IdUtil.simpleUUID().substring(0, 16);
    }
}
