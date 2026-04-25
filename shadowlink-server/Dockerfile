# ── Multi-stage Docker build for shadowlink-server ──

# Stage 1: Build with Maven Wrapper
FROM eclipse-temurin:21-jdk-alpine AS builder

WORKDIR /build
COPY . .
RUN chmod +x mvnw && ./mvnw clean package -DskipTests -pl shadowlink-starter -am

# Stage 2: Runtime — slim JRE image
FROM eclipse-temurin:21-jre-alpine AS runtime

LABEL maintainer="ShadowLink Team"
LABEL description="ShadowLink Java Backend Service"

WORKDIR /app

# Create non-root user
RUN addgroup -S app && adduser -S app -G app

COPY --from=builder /build/shadowlink-starter/target/shadowlink-server.jar app.jar

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1

RUN mkdir -p /app/logs && chown -R app:app /app
USER app

EXPOSE 8080

ENTRYPOINT ["java", \
    "-Xms256m", "-Xmx512m", \
    "-XX:+UseZGC", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-Dspring.profiles.active=${SPRING_PROFILES_ACTIVE:-prod}", \
    "-jar", "app.jar"]
