# 讯达通知中心

## 当前稳定版

`outputs/XundaNotify.exe` 是现有 Python/Tkinter 稳定版，可直接运行。

## Tauri/Rust 版

新版工程位于 `src-tauri`，界面位于 `src`。本机不需要安装 Rust；推送 `v*` 标签后，GitHub Actions 会在 Windows runner 上构建：

- `XundaNotify_*_x64-setup.exe`（NSIS）
- `XundaNotify_*_x64_en-US.msi`（MSI）

## 发布

```powershell
git add .
git commit -m "feat: add tauri windows app"
git push origin main
git tag v1.2.0
git push origin v1.2.0
```
