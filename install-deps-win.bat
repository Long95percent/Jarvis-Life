@echo off

cd shadowlink-web
npm install

cd ../shadowlink-ai
pip install -e ".[dev]"

cd ../shadowlink-server
mvnw.cmd clean install

echo ===== 依赖安装完成 =====
pause