# 讯达通知中心

一个面向 Windows 的桌面通知接收器，灵感来自“SmsForwarder -> WebHook -> Windows 通知”的实现思路。

## 功能

- 可视化启动/停止局域网 HTTP 服务
- 支持 `GET /?msg=...`、表单 POST 和 JSON POST
- 自动解析 `[微信]昵称:消息` 格式
- 有 `winotify` 时使用 Windows 原生 Toast，没有依赖时仍可运行
- 测试通知、消息计数、最近活动、配置持久化
- 支持自定义端口、应用名、提示音和免打扰模式

## 运行

```powershell
py app.py
```

将界面中的地址填入 SmsForwarder 的 WebHook，例如：

```text
http://电脑IP:8080/?msg=
```

也可以用浏览器测试：

```text
http://127.0.0.1:8080/?msg=%5B%E5%BE%AE%E4%BF%A1%5D%E5%B0%8F%E6%98%8E%3A%E4%BD%A0%E5%A5%BD
```

## 打包

```powershell
py -m pip install pyinstaller winotify
pyinstaller --noconsole --onefile --name XundaNotify app.py
```
