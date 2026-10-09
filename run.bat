@echo off
chcp 65001 >nul
title Discord 金融快讯极速推送服务

echo ==============================================
echo   Discord 实时金融快讯推送客户端 (F1-F5)
echo ==============================================

if not exist config.json (
    echo [提示] 正在根据模板生成 config.json...
    copy config.example.json config.json >nul
)

echo [1/2] 正在检查并安装 Python 依赖库...
python -m pip install -r requirements.txt -q

echo [2/2] 正在启动实时监控推送程序...
echo 程序已开启，每 10 秒轮询一次全网一手财讯，关闭本窗口即可退出。
echo ==============================================
python bot.py

pause
