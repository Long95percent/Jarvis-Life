package com.shadowlink.common.util;

import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

/**
 * AOP aspect that logs every controller request with method, URI, and elapsed time.
 */
@Slf4j
@Aspect
@Component
public class WebLogAspect {

    @Pointcut("execution(* com.shadowlink..controller..*(..))")
    public void controllerPointcut() {}

    @Around("controllerPointcut()")
    public Object around(ProceedingJoinPoint joinPoint) throws Throwable {
        long start = System.currentTimeMillis();

        ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();

        String method = "?";
        String uri = "?";
        if (attrs != null) {
            HttpServletRequest request = attrs.getRequest();
            method = request.getMethod();
            uri = request.getRequestURI();
        }

        Object result;
        try {
            result = joinPoint.proceed();
        } catch (Throwable t) {
            long elapsed = System.currentTimeMillis() - start;
            log.error("[{}] {} — FAILED in {}ms — {}", method, uri, elapsed, t.getMessage());
            throw t;
        }

        long elapsed = System.currentTimeMillis() - start;
        log.info("[{}] {} — {}ms", method, uri, elapsed);
        return result;
    }
}
