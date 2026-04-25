@echo off

start cmd /k "cd /d shadowlink-ai && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

start cmd /k "cd /d shadowlink-web && npm run dev"

start cmd /k "cd /d shadowlink-server && mvnw.cmd spring-boot:run -pl shadowlink-starter"

echo ===== 服务已启动 =====
pause