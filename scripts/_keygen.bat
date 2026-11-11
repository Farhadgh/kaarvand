@echo off
if exist "%USERPROFILE%\.ssh\kaarvand" (
  echo key-exists
  exit /b 0
)
ssh-keygen -t ed25519 -f "%USERPROFILE%\.ssh\kaarvand" -N "" -C "farhadtehrooni@gmail.com" -q
echo exit=%ERRORLEVEL%
