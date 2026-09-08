import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


cases = {
    "微信群聊": "from=com.tencent.mm&content=com.tencent.mm%0A%E4%B8%8D%E7%86%AC%EF%BC%9A29.9%E7%9A%84%E7%BE%BD%E7%BB%92%E6%9C%8D%E9%80%80%E6%AC%BE%0A%E8%82%A1%E7%BE%8A%E5%85%AD%E7%BE%A4%0AUID%EF%BC%9A10399",
    "微信私聊": "package=com.tencent.mm&content=%E5%BC%A0%E4%B8%89%EF%BC%9A%E4%BD%A0%E5%A5%BD",
    "QQ群聊": '{"package":"com.tencent.mobileqq","sender":"李四","group":"工作群","content":"收到"}',
    "钉钉私聊": "package=com.alibaba.android.rimet&sender=%E7%8E%8B%E4%BA%94&content=%E6%98%8E%E5%A4%A9%E5%BC%80%E4%BC%9A",
    "未知包名": "package=com.example.unknown&sender=%E8%B5%B5%E5%85%AD&group=%E6%B5%8B%E8%AF%95%E7%BE%A4&content=%E6%B5%8B%E8%AF%95%E6%B6%88%E6%81%AF",
    "无包名": "sender=%E5%B0%8F%E6%98%8E&content=%E4%BD%A0%E5%A5%BD",
}

for name, payload in cases.items():
    print(name, "=>", app.parse_message(payload))
