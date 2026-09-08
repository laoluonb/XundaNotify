from __future__ import annotations

import base64
import json
import logging
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import winreg
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import END, BooleanVar, Canvas, Entry, Frame, IntVar, StringVar, Text, Tk, Toplevel, messagebox
from tkinter import ttk

try:
    from winotify import Notification, audio
except Exception:
    Notification = None
    audio = None

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None


APP_NAME = "讯达通知中心"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "XundaNotify"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
LOG_FILE = CONFIG_DIR / "xunda.log"
ICON_DIR = CONFIG_DIR / "icons"
TOAST_APP_ID = "XundaNotify"

PACKAGE_NAMES = {
    "com.tencent.mm": "微信",
    "com.tencent.mobileqq": "QQ",
    "com.tencent.tim": "TIM",
    "com.tencent.wework": "企业微信",
    "com.alibaba.android.rimet": "钉钉",
    "com.ss.android.lark": "飞书",
    "com.whatsapp": "WhatsApp",
    "org.telegram.messenger": "Telegram",
    "com.sina.weibo": "微博",
    "com.android.mms": "短信",
    "com.google.android.gm": "Gmail",
}

PLATFORM_ICON_KEYS = {
    "微信": "wechat",
    "QQ": "qq",
    "TIM": "tim",
    "企业微信": "wecom",
    "钉钉": "dingtalk",
    "飞书": "feishu",
    "WhatsApp": "whatsapp",
    "Telegram": "telegram",
    "微博": "weibo",
    "短信": "sms",
    "Gmail": "gmail",
    "讯达": "xunda",
}

QQ_ICON_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAAQAElEQVR4nOzdCXgkZZkH8P9b1TOZmUwm6TDAcAzOkWQAWXF1AZWVYx8OQTnkXk4RISQZQGBR0d11xHVdj0XBSTJ5APFx3XXlEV1cL3R9xGtFFE8UmBwMhxwzkE4mc6er3n0rM7Ijc+Xoqq766v97ZtKdTufo6qp/vd9XVd9XADmj2N13WIhwiRdKM0T3gqIOkNkQ1AkwG6r2OWar2GP2NRE0RN+nQMluRuw56+yzdfbAiD1nBGOfYwQq0ddW22OPhX742HBrcz/ICQLKns7Vs+tl5A0ewiNsg32TPXKoQBYhQar6a1t9fm//Hww876G1bYseAmUOAyALPv98bcO6dScKwr+xt+x4e9MOQwpZJfG/qvip3T5YRuHH6zsWPg9KNQZASjV0rnytiJxiu9q32O0xyCALgqft47es6fDFobbmB0CpwwBIkYblvWfAw9s86Cn21hwAlyieCYEviSefK7U1PQJKBQZAlc3u7ttnOrTN9vSt9nbshxywyuAHqt7tQ3svug/nSQCqGgZAlTSu6D1UA7zfeuIvQm7pcwq5Db63otS6eBiUOAZAwuq6BpYUNLjFlvy5wuW/lep6FXzWmgifHm5vGQAlhitgQmb1rNqvJhj9pC3wC0G7ZM2D/9iihRt5BCEZDIC49ei0YtB3ky3oD9hns0DjoCO2ai4bnNt0G/sI4sUAiFH9ipUnegF67DDeQtDEqT6qnnelHTX4CSgWDIAYRD370zS8TSAXgKZEt/67A77/HnYUVh4DoMIau3rfpYpP/Ok8e6oQxQuhJ21DbU1fBVUMA6BSep6d1Ris/4rdOxkUG4V+srS6+b1YJiFoyhgAFVDftXKRD3zTFucSUAL0fwZrwrNwxcEjoClhAExRfVf/CT4C2/NLHSgx1jHQXw69U0eWLl4JmjQPNGlRe99D+G1u/MmzPdfighc+VOzuOxo0aQyAyVCVxs7eW+3eHbYi+qCqsGVfDw2/39jZdz5oUtgEmIRiV+99tuBOB6WHyk2DHU2fBE0IA2Ai7nlkeuOa6V+HyImg1LF+gfeV2ps/Bho3BsB42cZffLHmfltgx4FSiyEwMewDGCdu/Nlg79G/WBPtZtC4sAIYB7b5s8cqgaVWCXSCdosVwB4Uu1Z+ght/9th7ttyC+2LQbrEC2I1id2+bKLpAmaWip5XaWr4O2ikGwC40dPceJyG+J8IqKctUMYSCd3ipdfFToB1w5d6JOSv6m70Q93Hjz76xqzKD4L+xTAugHXAFf4WGTz3RUAjDb1htNAfkBIG8prh373LQDhgAryA1o1+wm2aQU0SktaGz/yzQn2EfwHbY6ec6HUFZDh28tvkZ0BhWANtE7X7b+G8FOUzq4OuXo4u5QGMYANv4QXiv3cwAuU3kqMau/htBYxgAGDvT72brLf4LUE7oLTO7H3dr7sVJyn0ANHQ/sQCKD4LyQzBzpnp3gRgAouW7be9fA8qbkxuX956HnMt1AESHhXiFX46JfioazRk5lt8AWKaeSPCvoPwS2b8YrP8Aciy3AVDct69VIAtA+aa4sbGzbz5yKp8BEJV9qreAcm9r/4/m9vyPXAZAsbzhetv7zwVRRHBO/fLe1yGH8hcA0d5f9CYQbcfz8lkR5i4AGsP1N42NJ0+0HasI39rQufK1yJlcBUCxp78eIW4A0U7YjuEjyJl8VQBlXcrr/GlXROTU2Z0rD0GO5CcA7lFfoNeAaDemCd6NHMlNABRf7D3f9v77gmh3VC7DXY/lZrLX/FQACvb80x5F5wUUN/vtyIlcBMCc5SuPsvZd7np4adI6kBO5CICCyFUgGic7GjC/fsXKXEwA634A3Pr0TAUuAtEE+KFciRxwPgCKNRsv5fX+NFEKPbNu+TN7wXHOB4Bt/O8E0QQJZJovG5yfW9DpAKjv6V1sb+WRIJoEC4Hz4TinA8ArywUgmiSrHt9Ye8eA0+eOON4EUOcTnOJVsyV0uhngbADUdQ0s4VDfNHXhuXCYswFQQHA2iKZK5KhZPav2g6OcDQBRPR1EFVATlE+Do5wMgDl3Pt2owt5/qpSQAZAl3paNZwhnPqbKOQk9Og0OcjMAgLeCqEIEMr0Y9J8AB7kXANHUz4qTQVRR4fFwUAGOaejqPdx6bmeDqIJE3ZxCzr0KQOQ4EFWYQl6Pzz9fC8c4FwCuJjVVlwi84tr1x8IxDlYADACKiRceDcc4FQB1PU8czEk/KC6iegQc41QA+OXRN4AoJi6eXOZUAIh4R4EoJlF1uXWMCXe41QegISsAipUXilPNAMcqAA79TTHT0KlpxJ0JgIYVA4eDKGai4tR65kwASBAcBqKYqehfwSEuNQEYABQ7gTS6NE6gSwHwahAloBCUXwNHuBMAgkNBlAA7EtACR7gRAMs0eh0LQJQA6whshiOcCIA58wYWC+CDKAEqoTMnAzkxHoAfahOIEiIKZwLAiQpAAQYAJUgWwBFOBIAHXQSipAhm1nY+MQ8OcKMTUHEgiBLke3oQHOBGAAgDgJLlherEOscKgGhSgvlwgBudgIIDQJQoYQCkQdQZw1mAKGkicOJ6gMwHwHQvmAuihNkeZ284IPMBoKp7gShhCjix48l+H4B6DABKnroRAJk/FdgDKwBKnjiy3mW/CSDaCKKkOTL/pAuHAeeAqArqu54sIuMyHwCiypmAqSr88pbMTxbqwOXAnAqcqmO0ppD5dS/7fQAAA4CqwtOQAVB1os7N2U7Z4IUyExnnQB8AZoCoCkINGADVpiJODGtG2eOpl/l1z4WNhwFAVaEIpyHjst8EgGb+TaBsUl8dOJM241TZBKDq8OBlfueT+Y1HrC8GRNWgrACqToEREFWB7XwyfwTKhfJ5LYiqwHY+Ncg4FwJgGERVIIrpyDhWAEST5EIF4MKpwAqiapDsDwqS7QCwY4Cici6IqsA6AS+K1kFkWKYDoKFr4O32LjgxRxtlkezX0N1/BjIs0wHgIWwFURVZCzTT62Bmy5fGzr75KvokJwWhatLon+8tKLUufgoZlNkKwDb+Dm78VG1j62CQ3Uo0mwFwj/rW+fIuEKWCXpXVzsBMBkDjmv5zRITzAVAqCGRu/Yres5BBmQwARbY7Xsg9fohMrpOZK1vqu1Yu8iH9IEoRHeuWklcNdjQ9jQzJXAXgq3ctiFIm6gxUCa9BxmQrAO55ZLoF7eUgSiPFO8c6qDMkUwHQ8FLNxRa1nAqMUinqmC6u6bsAGZKpAPBCtIEo1fRqZEhmOgEbOle+1hP5FYhSLvDRNNzanImO6uxUACIdIMoAL9DrkBHZqAB6np3VWF632kKA04BR6qliqBRgHq5t3oyUy0QF0FjecBE3fsoKETQUfZyDDMhGE0BCnvdP2SLIxDqb+ibAnBX9zYUwXAmijAmlsHCobeEqpFjqK4BCECwFUQaJlq9CyqU7AJZpQUUuA1EGieplab9MONUBUNy3/xxbevUgyiKR/YvdA6cixdJdAWi2zqoi2oGme7Sg1JYn9T29i/0AfSDKMFWEW1A4YH3HwueRQqmtAPwyeOYfZZ4IvBqvnNoqIJ0BMHbZL64AkQuiocNT2hmYygAovlhzHi/7JXfIfsUVvW9FCqWzAsj4ZAtEOwgllecEpK4s4Zl/5KKoM3BzYdqBG1oXPIcUSV0F4IdB6s+eIpqosc7AYPQdSJl0BcAyLdjHd4DIRapXImVSFQANew+cHk2yACIHicjChq7eY5EiqQoAQcBDf+Q0iUYOTpHUdALWdj4xbzrKf4zaSiBy16ZBv3YvtO6/ASmQmo1tupQv58ZPOTCjsbz+b5ESqdngRPVSEOWACi5GSqSiCVC/vPd1voeHQZQD0TyCmyScv7FtyR9RZamoAGzjvwREORHNIzhDvVRUAdUPAFWr/nERiHLEQiAVTd6qB0BjV//J1vm3N4jy5dCGFQOHo8qqHgC2/78QRDkkQVj1db+6AbBMCwI9E0R5JFr1mYSrGgAN+/afZkuhDkQ5ZP0AB83pHjgSVVTVALDev/NBlGOeBlXdBqoXAHc/MUMUp4MoxzxFVfsBqhYAjRuCM6wGmgmiPBPMa+zsexOqpIpNAM3E7KlECTgPVVKdAOjRafYxlYMkEiWven1hVQmAhqDvFJb/RNtYM6DY3Xc0qqAqAeCpvh1E9DIJcS6qIPkAWKaeJd7ZIKLtVKcZkHgA1O/bfxxP/iF6hSo1AxIPAF/1NBDRDlT1LCQs8QBQnvtPtFOe4m1IWKIBUNc1sEQgC0BEOxK01HetXIQEJRoA0zRMPOGIssR2kImeHp9oAKgoA4BoNzxooifIJTco6F2P1RU3+yX7hT6IaKcUCEp+7Zyk5g1IrAKo3+SfzI2faPeibaQh2HASEpJYAIjgZBDRHonqiUhIYgFghzjeAiLaI6sCTkBCEgmAOZ19TfaqDgQR7ZkdDpx9e28iI2UnEgC+l1xJQ+SCQiGZI2aJBICEDACiiRBIIs2AApIgybVpiFwg0GORgNgrgNmdKw/h1X9EEyUHNCwfeBViFnsATBepykgnRFknUo59sND4+wBUGQBEkyKxB0D8fQCsAIgmK/YAiPVagLrlz+w1zdv4IohoUgb92to4rwuItQlQwOajQESTVgw2vR4xijUARMKqTnxIlHWC4AjEKNYAUAEDgGgKFJrdABAFOwCJpkSyGQDFnv6DrH6ZAyKaNOulX9x4e29s21F8FUCgr0ZMVDFk//tAlAaqj9rH2Hrqy54egpjEFgBW/h+KuHjSZh8ZAJQWj1p/198hJp4X37YUYx+AxvRH60Oltqb/tIQZAlEKhCKDpbbmbrvbixhYMyB7FYBtoIeh8jaUPf/irXc9BgClgmDrzqgc6iWIR/YqAAWaUHnXrb168daUVVYAlBZSij6uXdryM1vxP4QKk3i2pTHxBMBdj9UJpBEVpKo/HmxvvnO7h4ZBlA4vr4uDezd92Dqof48Ksp+3GDGJJQAatviVTqwNqoWLt39AIc+CKAVUtlsXz5PA+gQuQwWJSGFWz6r9EIN4KoDQW4gKinpYh5YuevLPHlN9BEQpoBr+ZvvPh9ubHrYm8MdQQTNGRxcgBvEEgOgBqBBbkA9s62H9M8NbZjwKompTXT/c3jLwyodL7c3vQwWPCgS+7o8YxBIAouG+qATFRvjezsupG+ZvREyHXYjGy8r/3+zqa2XxL9axfdjUeZB9EIOYjgJU5o8NoTeXWhc/tcsnqP4ORNWk+PWuvrS2bdFDdtOFSvwaRSzzBMRTAUDnYqoU3xnqaLltt8/x5LcgqqbdVACRkl/7nkocFajINrUTMfUBYEqjACt0lRa88/b0vBAMAKquMNRf7PYJrftvKKt3lq3VI5gCUZmFGMQSAHaIbkp/bBjK2Vb67/k4/yb/+yCqEtuzrxle2vzLPT1vZOnilYHgckyBitYiBjH1AUz+jw2B68ezUCND1y8csmrhRyCqBsH9433qcFvLvbZu34nJUpmJGMQTACqT+rnW31cadQAAB8hJREFUXfqtofbmT0/wm74OompQ/eZEnj7k116HlB25Smx68D1SvBBMn3HxhL/P8yb0JhBVQnR4TwL5xoS+KRrd18OZVrVuwQRZJ2CIGMTVCVjGBKn456591/xBTFCprekRezeeAVGSFA8OXtu8FhM0eHXzH+zIwbsxQdavNooYxNQEwISu1LPe/GtL7Ysm3Za3NP4vECXIOuUmXXlGZ7ZaB+LnJ/RNgpcQg3jOAxAd955cVT8y1N70GUyBCr4MogR5oXwVU1DqaL7MmgLjbkJYEyA7AWBb5FPjeprijlJHy99jiqzj8Ad28wcQJSC6PmVwafOUT+4pbZp5rm0EPxvXk1VWIQbxnAcg6N/jc4CvWQpehQqx37kcRAkIFZ2ohBvmbyzXzDwV4zgyEEo8Y2DGdBTA3+0Zelb2/7C0acYFqKDS9OALYxcPEcVKnxvuaK5YkzPq+A5D/8Q9dWQP1QTjOjdmomIJgNLsWbv8Y6ORfUqF2adsu5qvcq44eMSqgM+CKEa29+9GhUVjXQQFHGch8PzOvm5N5d9F6zdiEE8FcOm89fZH3/fKh63s/zdr8785rtlOy36BzQCKVTmQFYjBcGuzNZvlSNtGfvXKr9kRh3sQk/gGBVW99eX70FX2Ki4otTdfihiNtC58zH7x90AUA9s4v7Du2uY1iMlgR9PTto28btvAohu2/dK1ga+xhE5EEKPG7t6TNdRG2+t/EQkpdvcdLdbMAFGFjYbekujCHiThrsfqGjf756vIg2Mnu8Uk1gColsbO3vvtlZ0EokpR/dxgR8uUruhLo/RcC1BBKv5NIKoQa8KObvR0yuerpJGTAVBqX/RbS+yvgKgyVmxsW/JHOMjJAIiMSuH9diQiliuoKFc2haj5IBzlbACMtC963PoB/h1EU2A9/7cOt7+qBEc5GwARDf1/ANHkrYbvfRwOczoAojOsVNAOokkIPL14XGNTZpjTARDZNqvQuMduI4qoas/w1S3fheOcD4DIqB9GM7Q4246jyrLDfgOlQK5DDuQiAEZal7xoAfAOEO1BdORIRc7Btc2bkQO5CIDIUHvz16KzuUC0G9Zn9KGhtuZfISdyEwCRQTRcY5XAuEYrovyxvf9PbUdxC3IkVwGAjn3Wjaq+xd7pdSDanuL5LdP9tyNn8hUAZl1Hy6MB5OxKTdtMDlBs1NA7af2Vi15AzuQuACLDHc3fsSrgfSDC2ERW55auWZzLqeZzGQCRUkfLx6MBHkC5Fqr+Y6l98cRm+HFIbgMgUlrddLlVAj8H5ZTeO9TR8mHkWK4DAMukPFrQU60SeBqUL4pfDM7dciFyLt8BgG0nCUnhGB4ezA+F/lYL3gk477AJT9LpGieHBJuMWT2r9qspb/mJiCwEOcuC/uFSTXB8XMNsZ03uK4A/2dC64LnRQI4Cpxhz2YMlv/YYbvz/jwGwnWjIZ/W9N0V7CZBTrOz/0eDMwvFxzUmRVWwC7EzPs7OKwbpvC+TNoMyzQP9Wae7mM9nm3xEDYFc6V89uxPDDtoRaQJmlil+WOppfD9opBsArNC7vfaMtlSvs7rl2OweUeWNjQajeg9DvzOsZf7vCADAzux8/YEboXSKCS+zTQ0HOiioCW+3vHvVwz7q2ptXIudwGQH3Xk0VPN59ndy+0Q3/HgPLo/hDyxSGdc290pShyKHcBUOzs/2tIeKO98DNBtE10XYh4+Ojg1c25OgycmwBoWN57hpX477X/bwTRLtjhwm9oiI8PLW35IXLA+QAodg3Yobygy17oYSAaJ6sIHhhVbY/Gj4DDnA2AWZ95av8Z/uZ/srvOzehKybEg+GipJvioq2cPOhkAxa7ef7YXdjOIKsCaBYN284FSe8sKOMapAGi8vfdA+PoViBwBoorTewdnz7kMl85bD0c4EwANKwYO94Lg2/aK5oEoJqr663JBT4wuI4cDnAiAuuX9LdO84Bf2cupAFDfVxwZnhEe60C/gxNWABS/8Ljd+SozIwY2bvbvhgMwHQLGzb6mVMQeBKFFydkN3718i4zIfAILwUhBVgahmfkzBzAeACjiEF1WHSuYrTwf6AOR5EFVH5q8mdKAC0DtAVAVWfX4XGZf5ABhqa7k9BO4EUYIU6B6bcj7j3DkRyHpkRXGDvaBz7NMZoF1S6IsCKdndl+yYtq+Qoj1aFJG9QLs2Nqu0fGlU/E+MtC96HA5w81qA7r7DNNDFIjhEoEdaqXasrfCNcMcmVV1vx6PXS3QLWW+v0VbOsfvrbO80YqXdOtvShzVqp4r3ZBiGzwW+PLOnUXBqO5+YV/DDAyXUAy1QD7QVZB97eI797Nn2s+qiW/u9tfbYbPvdtTp2X2sdW75RSr5gy/QBUfm5euHjZS30urLRby9/IwL1PDurLtg035PwAE91f0v1/W3lnfWnL9tKvpcFx752u4+FxzzbO9otiuP98aoYsu/bYN8XDT+98eX7ohtsZdpoP9fui93XjdHGat8R7uznhKJl2yO/ZBvhi/aE1dH9LQVvTdqnsI6uwqzxy3NVw71gC3hnz5EQddZ3M9de2962rC1UxMJF7T2Qmba8ZunW92PH+2pfFzRg/FbbX7DGlvFLtszH/hb7uNk27GgZPmP316gnz40t323vg5S9l7TsPT10/cIh5ADHBCTKMU4MQpRj/wcAAP//5K6yNAAAAAZJREFUAwDIkjLPHadKSQAAAABJRU5ErkJggg=="
)


def setup_logging() -> logging.Logger:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("xunda")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    return logger


LOGGER = setup_logging()


@dataclass
class AppConfig:
    port: int = 8080
    app_id: str = APP_NAME
    sound: bool = True
    launch_on_start: bool = False
    quiet_mode: bool = False
    notification_mode: str = "both"


def load_config() -> AppConfig:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return AppConfig(**{k: data[k] for k in asdict(AppConfig()) if k in data})
    except Exception:
        return AppConfig()


def save_config(config: AppConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def clean_body(text: str) -> str:
    """Remove SmsForwarder transport metadata while preserving chat/group text."""
    text = urllib.parse.unquote_plus(str(text or "")).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)&?timestamp\s*[:=]\s*\d+", "", text)
    kept: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"(?i)^(?:uid|用户uid|user_?id)\s*[:：=]", stripped):
            continue
        if re.match(r"(?i)^(?:from|package|pkg|app包名)\s*[:：=]", stripped):
            continue
        if re.fullmatch(r"(?i)[a-z][\w]*?(?:\.[a-z0-9_]+){2,}", stripped):
            continue
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", stripped):
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip(" \t\n&;,，。")


def clean_title(text: str) -> str:
    title = urllib.parse.unquote_plus(str(text or "")).replace("\r", "\n")
    title = re.sub(r"(?is)^.*?(?:from|package|pkg)\s*[:=]\s*com\.tencent\.mm\s*&?\s*(?:content\s*[:=]\s*)?", "", title)
    lines = [line.strip() for line in title.splitlines() if line.strip()]
    lines = [line for line in lines if not re.fullmatch(r"(?i)[a-z][\w]*?(?:\.[a-z0-9_]+){2,}", line)]
    return (lines[-1] if lines else "微信消息")[:80]


def platform_from_title(title: str) -> str:
    cleaned = clean_title(title)
    for name in sorted(set(PACKAGE_NAMES.values()), key=len, reverse=True):
        if cleaned == name or cleaned.startswith(f"{name}-"):
            return name
    return "讯达"


def notification_body(text: str) -> str:
    cleaned = clean_body(text)
    return cleaned if cleaned and cleaned not in ("收到一条新消息", "收到一条空消息") else "新消息"


def application_name(package_name: str, supplied_name: str = "") -> str:
    if supplied_name and supplied_name.lower() not in (package_name.lower(), "null", "none"):
        return clean_title(supplied_name)
    package = package_name.strip().lower()
    if package in PACKAGE_NAMES:
        return PACKAGE_NAMES[package]
    return ""


def format_notification_title(
    sender: str,
    body: str,
    package_name: str = "",
    app_name: str = "",
    group_name: str = "",
) -> tuple[str, str]:
    sender = clean_title(sender)
    body = clean_body(body)
    known_apps = set(PACKAGE_NAMES.values())
    sender_name = sender.rsplit("-", 1)[-1].strip()
    body_lines = body.splitlines()
    if body_lines and body_lines[-1].strip() == sender_name:
        body = "\n".join(body_lines[:-1]).strip() or "新消息"
    if any(sender.startswith(f"{name}-") for name in known_apps):
        return sender, body

    lines = body.splitlines()
    group = clean_title(group_name) if group_name else ""
    if not group and len(lines) >= 2:
        candidate = lines[-1].strip()
        looks_like_label = (
            1 <= len(candidate) <= 40
            and candidate != sender
            and not candidate.startswith(("http://", "https://", "#小程序://"))
            and not re.search(r"[。！？!?，,；;]$", candidate)
        )
        if looks_like_label:
            group = candidate
            body = "\n".join(lines[:-1]).strip() or body

    software = application_name(package_name, app_name)
    if not software:
        title = sender if sender not in ("微信消息", "消息", "通知") else (group or "消息")
    elif "-" in sender and not group:
        # Migrate an older stored title such as "群名-人名".
        title = f"{software}-{sender}"
    elif sender in ("微信消息", "消息", "通知"):
        title = f"{software}-{group}" if group else software
    elif group:
        title = f"{software}-{group}-{sender}"
    else:
        title = f"{software}-{sender}"
    return title[:80], body


def load_history() -> list[tuple[str, str, str]]:
    try:
        rows = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        cleaned = []
        for row in rows[-500:]:
            title, body = format_notification_title(str(row["title"]), str(row["body"]))
            cleaned.append((str(row["time"]), title, body))
        cleaned = [(t, title, notification_body(body)) for t, title, body in cleaned]
        save_history(cleaned)
        return cleaned
    except Exception:
        return []


def save_history(history: list[tuple[str, str, str]]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    rows = [{"time": t, "title": title, "body": body} for t, title, body in history[-500:]]
    HISTORY_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def parse_message(raw: str) -> tuple[str, str]:
    original = str(raw or "").strip()
    text = urllib.parse.unquote_plus(original).strip()
    if not text:
        return "微信消息", "新消息"

    lowered: dict[str, str] = {}
    if original.startswith("{"):
        try:
            obj = json.loads(original)
            lowered = {str(key).lower(): str(value) for key, value in obj.items() if value is not None}
        except Exception:
            pass
    if not lowered and "=" in original:
        values = urllib.parse.parse_qs(original, keep_blank_values=True)
        lowered = {key.lower(): items[-1] for key, items in values.items() if items}

    if lowered:
        message_keys = ("content", "通知内容", "msg", "message", "text", "body")
        message_value = next(
            (lowered[key] for key in message_keys if lowered.get(key)),
            "",
        )
        sender_value = next(
            (lowered[key] for key in ("sender", "nickname", "发送人", "title", "通知标题", "name") if lowered.get(key)),
            "",
        )
        package_name = next(
            (lowered[key] for key in ("package", "pkg", "from", "app_package", "app包名") if lowered.get(key)),
            "",
        )
        supplied_app = next(
            (lowered[key] for key in ("app_name", "application", "app应用名", "软件名") if lowered.get(key)),
            "",
        )
        group_name = next(
            (lowered[key] for key in ("group", "group_name", "conversation", "chat", "群名") if lowered.get(key)),
            "",
        )
        if any(key in lowered for key in message_keys) and message_value != text:
            parsed_title, parsed_body = _parse_message_content(message_value)
            if sender_value and parsed_title in ("微信消息", "消息", "通知"):
                parsed_title = sender_value
            return format_notification_title(parsed_title, parsed_body, package_name, supplied_app, group_name)

    package_match = re.search(r"(?i)\b(?:from|package|pkg|app包名)\s*[:=]\s*([\w.]+)", text)
    package_name = package_match.group(1) if package_match else ""
    parsed_title, parsed_body = _parse_message_content(text)
    return format_notification_title(parsed_title, parsed_body, package_name)


def _parse_message_content(text: str) -> tuple[str, str]:
    text = urllib.parse.unquote_plus(str(text or "")).strip()

    # Remove common forwarding metadata even when the template is not a valid query string.
    metadata_keys = r"(?:uid|user_?id|from|device_?id|package|pkg|sim_?id)"
    text = re.sub(rf"(?i)(?:^|[&;,\s]){metadata_keys}\s*[:=]\s*[^&;,\s]+", " ", text)
    text = clean_body(text)
    if not text:
        return "消息", "新消息"
    lines = text.splitlines()
    if lines and re.fullmatch(r"(?i)com\.tencent\.mm", lines[0].strip()):
        text = "\n".join(lines[1:]).strip()
    # SmsForwarder commonly sends: [微信]昵称:消息
    colon_match = re.search(r"[:：]", text)
    if colon_match:
        prefix = text[:colon_match.start()]
        body = text[colon_match.end():]
        if "]" in prefix:
            prefix = prefix.split("]", 1)[1]
        title_lines = [line.strip() for line in prefix.splitlines() if line.strip()]
        title = title_lines[-1] if title_lines else "微信消息"
        return clean_title(title), notification_body(body)
    return "消息", clean_body(text)


class NotifyHandler(BaseHTTPRequestHandler):
    server_version = "XundaNotify/1.0"

    def _reply(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        raw = parsed.query
        if raw:
            self._notify(raw)
        else:
            self._reply(200, {"ok": True, "service": APP_NAME, "hint": "Use /?msg=..."})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        raw = body
        self._notify(raw)

    def _notify(self, raw: str) -> None:
        title, body = parse_message(raw)
        app: "NotifyApp" = self.server.app  # type: ignore[attr-defined]
        LOGGER.info(
            "收到 WebHook：来源=%s，标题=%s，正文长度=%s",
            self.client_address[0] if self.client_address else "未知",
            title,
            len(body),
        )
        app.events.put(("message", title, body))
        self._reply(200, {"ok": True, "title": title, "message": body})

    def log_message(self, fmt: str, *args) -> None:
        return


class NotifyApp:
    def __init__(self, root: Tk):
        self.root = root
        self.config = load_config()
        self.events: queue.Queue = queue.Queue()
        self.history: list[tuple[str, str, str]] = load_history()
        self.popups: list[Toplevel] = []
        self.history_tree: ttk.Treeview | None = None
        self.history_view: Frame | None = None
        self.overview_view: Frame | None = None
        self.settings_view: Frame | None = None
        self.log_view: Frame | None = None
        self.log_text: Text | None = None
        self.log_file_signature: tuple[tuple[str, int, int], ...] = ()
        self.tray_icon = None
        self.exit_requested = False
        self.toast_icon_paths = self._prepare_toast_icons()
        self.toast_icon_path = self.toast_icon_paths.get("讯达")
        self._register_windows_toast_app()
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.running = False
        self.ip = local_ip()
        self._build_style()
        self._build_ui()
        self._refresh_activity()
        self._setup_tray()
        self._poll_events()
        self._poll_log_file()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        LOGGER.info("应用启动，监听地址 %s:%s", self.ip, self.config.port)

    def _build_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 6))
        style.configure("Accent.TButton", background="#31a8d2", foreground="#ffffff", borderwidth=0, padding=(13, 7), font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#43b5df")], foreground=[("active", "#ffffff")])
        style.configure("Ghost.TButton", background="#223242", foreground="#c9d8e3", borderwidth=0, padding=(12, 7))
        style.map("Ghost.TButton", background=[("active", "#2c465a")], foreground=[("active", "#ffffff")])
        style.configure("Nav.TButton", background="#101b27", foreground="#8fa6b8", borderwidth=0, anchor="w", font=("Segoe UI", 10), padding=(14, 10))
        style.map("Nav.TButton", background=[("active", "#1d3445")], foreground=[("active", "#ffffff")])
        style.configure("NavActive.TButton", background="#1c526c", foreground="#ffffff", borderwidth=0, anchor="w", font=("Segoe UI", 10, "bold"), padding=(14, 10))
        style.map("NavActive.TButton", background=[("active", "#256782")], foreground=[("active", "#ffffff")])
        style.configure("Treeview", background="#172432", fieldbackground="#172432", foreground="#e1edf5", rowheight=42, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#203342", foreground="#a9bfce", relief="flat", font=("Segoe UI", 9, "bold"), padding=(8, 9))
        style.map("Treeview", background=[("selected", "#285a78")], foreground=[("selected", "#ffffff")])

    def _build_ui(self) -> None:
        self.root.title(APP_NAME)
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)
        self.root.configure(bg="#0d1721")

        sidebar = Frame(self.root, bg="#101b27", width=244)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = Frame(sidebar, bg="#101b27")
        brand.pack(fill="x", padx=24, pady=(28, 34))
        icon = Canvas(brand, width=44, height=44, bg="#101b27", highlightthickness=0)
        icon.create_oval(3, 3, 41, 41, fill="#26a6d1", outline="")
        icon.create_text(22, 21, text="✦", fill="white", font=("Segoe UI", 20, "bold"))
        icon.pack(side="left")
        text_box = Frame(brand, bg="#101b27")
        text_box.pack(side="left", padx=11)
        # Keep the textual identity compact and readable at typical Windows DPI.
        name = ttk.Label(text_box, text="讯达", foreground="#f5fbff", background="#101b27", font=("Segoe UI", 17, "bold"))
        name.pack(anchor="w")
        ttk.Label(text_box, text="通知中心", foreground="#7e99ac", background="#101b27", font=("Segoe UI", 9)).pack(anchor="w")

        ttk.Label(sidebar, text="工作台", foreground="#668195", background="#101b27", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=24, pady=(0, 10))
        self.nav_buttons: list[ttk.Button] = []
        for label, command in [
            ("⌂  总览", self._focus_overview),
            ("◷  消息历史", self._focus_history),
            ("⚙  设置", self._open_settings),
            ("≡  运行日志", self._focus_logs),
        ]:
            b = ttk.Button(sidebar, text=label, command=command, style="Nav.TButton")
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons.append(b)
        sidebar_spacer = Frame(sidebar, bg="#101b27")
        sidebar_spacer.pack(expand=True, fill="both")
        ttk.Label(sidebar, text="服务状态", foreground="#668195", background="#101b27", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24, pady=(0, 4))
        ttk.Label(sidebar, text="●  本机通知服务", foreground="#66d2b0", background="#101b27", font=("Segoe UI", 9)).pack(anchor="w", padx=24, pady=(0, 4))
        ttk.Label(sidebar, text="v1.1.0  ·  Windows", foreground="#52697a", background="#101b27", font=("Segoe UI", 8)).pack(anchor="w", padx=24, pady=(0, 22))

        self.main = Frame(self.root, bg="#0d1721")
        self.main.pack(side="left", fill="both", expand=True)
        self._build_overview()
        self._build_history_view()
        self._build_settings_view()
        self._build_log_view()
        self._show_view("overview")

    def _card(self, parent, title: str, value: str, accent: str, subtitle: str) -> Frame:
        box = Frame(parent, bg="#18232e", highlightthickness=1, highlightbackground="#263746")
        box.pack(side="left", fill="both", expand=True, padx=(0, 12))
        Frame(box, bg=accent, height=3).pack(fill="x")
        ttk.Label(box, text=title, foreground="#8ba2b4", background="#18232e", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(16, 2))
        var = StringVar(value=value)
        ttk.Label(box, textvariable=var, foreground="#f4f8fb", background="#18232e", font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=18)
        ttk.Label(box, text=subtitle, foreground="#668093", background="#18232e", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(2, 16))
        box.value_var = var  # type: ignore[attr-defined]
        return box

    def _build_overview(self) -> None:
        self.overview_view = Frame(self.main, bg="#0f1720")
        self.overview_view.pack(fill="both", expand=True)
        parent = self.overview_view
        header = Frame(parent, bg="#0f1720")
        header.pack(fill="x", padx=34, pady=(28, 20))
        ttk.Label(header, text="消息接收台", foreground="#f4f8fb", background="#0f1720", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(header, text="把手机上的重要消息，安静地送到你的 Windows 桌面。", foreground="#7f96a8", background="#0f1720", font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 0))
        self.status_pill = ttk.Label(header, text="●  服务未启动", foreground="#ffb36b", background="#0f1720", font=("Segoe UI", 10, "bold"))
        self.status_pill.pack(anchor="e", pady=(0, 4))

        cards = Frame(parent, bg="#0f1720")
        cards.pack(fill="x", padx=34)
        self.server_card = self._card(cards, "服务状态", "未启动", "#f0a35e", "等待开始接收")
        self.messages_card = self._card(cards, "今日消息", "0", "#4bc0c8", "条通知已送达")
        self.address_card = self._card(cards, "局域网地址", f"{self.ip}:{self.config.port}", "#9b8cff", "提供给手机端 WebHook")

        content = Frame(parent, bg="#0f1720")
        content.pack(fill="both", expand=True, padx=34, pady=24)
        left = Frame(content, bg="#18232e", highlightthickness=1, highlightbackground="#263746")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        top = Frame(left, bg="#18232e")
        top.pack(fill="x", padx=20, pady=(18, 8))
        ttk.Label(top, text="接收地址", foreground="#f4f8fb", background="#18232e", font=("Segoe UI", 12, "bold")).pack(side="left")
        self.toggle_button = ttk.Button(top, text="启动服务", command=self.toggle_server, style="Accent.TButton")
        self.toggle_button.pack(side="right")
        ttk.Label(left, text="将下方地址填入 SmsForwarder 的 WebHook，支持 GET / POST。", foreground="#7f96a8", background="#18232e", font=("Segoe UI", 9)).pack(anchor="w", padx=20)
        addr = Frame(left, bg="#223242")
        addr.pack(fill="x", padx=20, pady=14)
        self.address_var = StringVar(value=f"http://{self.ip}:{self.config.port}/?msg=")
        Entry(addr, textvariable=self.address_var, bg="#223242", fg="#d9edf7", insertbackground="white", relief="flat", font=("Consolas", 10)).pack(side="left", fill="x", expand=True, padx=12, pady=11)
        ttk.Button(addr, text="复制", command=self.copy_address).pack(side="right", padx=8)
        ttk.Button(left, text="发送测试通知", command=self.send_test, style="Ghost.TButton").pack(anchor="w", padx=20, pady=(0, 18))

        right = Frame(content, bg="#18232e", highlightthickness=1, highlightbackground="#263746", width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        ttk.Label(right, text="最近活动", foreground="#f4f8fb", background="#18232e", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=18, pady=(18, 5))
        ttk.Label(right, text="最新收到的通知会显示在这里", foreground="#6f8798", background="#18232e", font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=(0, 10))
        self.activity = ttk.Treeview(right, columns=("time", "title"), show="headings", height=11)
        self.activity.heading("time", text="时间")
        self.activity.heading("title", text="消息")
        self.activity.column("time", width=62, anchor="center")
        self.activity.column("title", width=200)
        self.activity.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _focus_overview(self) -> None:
        self._show_view("overview")

    def _focus_history(self) -> None:
        self._show_view("history")

    def _focus_logs(self) -> None:
        self._show_view("logs")

    def _show_view(self, view: str) -> None:
        views = {
            "overview": self.overview_view,
            "history": self.history_view,
            "settings": self.settings_view,
            "logs": self.log_view,
        }
        for page in views.values():
            if page:
                page.pack_forget()
        target = views.get(view, self.overview_view)
        if target:
            target.pack(fill="both", expand=True)
        self._set_nav_active({"overview": 0, "history": 1, "settings": 2, "logs": 3}.get(view, 0))
        if view == "history":
            self._refresh_history_view()
        elif view == "logs":
            self._refresh_log_view()

    def _set_nav_active(self, index: int) -> None:
        for i, button in enumerate(self.nav_buttons):
            button.configure(style="NavActive.TButton" if i == index else "Nav.TButton")

    def _build_history_view(self) -> None:
        self.history_view = Frame(self.main, bg="#0f1720")
        header = Frame(self.history_view, bg="#0f1720")
        header.pack(fill="x", padx=34, pady=(28, 20))
        ttk.Label(header, text="消息历史", foreground="#f4f8fb", background="#0f1720", font=("Segoe UI", 24, "bold")).pack(side="left")
        self.history_count_label = ttk.Label(header, text="共 0 条", foreground="#7f96a8", background="#0f1720", font=("Segoe UI", 10))
        self.history_count_label.pack(side="left", padx=14, pady=(8, 0))
        ttk.Button(header, text="清空历史", command=lambda: self._clear_history(None), style="Ghost.TButton").pack(side="right")
        panel = Frame(self.history_view, bg="#18232e", highlightthickness=1, highlightbackground="#263746")
        panel.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        tree = ttk.Treeview(panel, columns=("time", "title", "message"), show="headings", selectmode="browse")
        tree.heading("time", text="时间")
        tree.heading("title", text="来源")
        tree.heading("message", text="消息内容")
        tree.column("time", width=110, anchor="center")
        tree.column("title", width=180)
        tree.column("message", width=550)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=14)
        scrollbar.pack(side="right", fill="y", padx=(0, 14), pady=14)
        self.history_tree = tree
        detail = Frame(self.history_view, bg="#18232e", highlightthickness=1, highlightbackground="#263746")
        detail.pack(fill="x", padx=34, pady=(0, 28))
        self.history_detail_title = ttk.Label(detail, text="选择一条消息查看完整内容", foreground="#8da3b4", background="#18232e", font=("Segoe UI", 10, "bold"))
        self.history_detail_title.pack(anchor="w", padx=16, pady=(12, 4))
        self.history_detail_text = Text(detail, bg="#18232e", fg="#cbd9e3", relief="flat", wrap="word", height=4, font=("Segoe UI", 10))
        self.history_detail_text.pack(fill="x", padx=12, pady=(0, 12))
        self.history_detail_text.configure(state="disabled")
        tree.bind("<<TreeviewSelect>>", lambda _event: self._show_history_detail(tree))

    def _refresh_history_view(self) -> None:
        if not self.history_tree:
            return
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        for t, title, msg in self.history:
            self.history_tree.insert("", END, values=(t, title, msg))
        self.history_count_label.configure(text=f"共 {len(self.history)} 条")

    def _show_history_detail(self, tree: ttk.Treeview) -> None:
        selected = tree.selection()
        if not selected:
            return
        values = tree.item(selected[0], "values")
        self.history_detail_title.configure(text=f"{values[1]}  ·  {values[0]}")
        self.history_detail_text.configure(state="normal")
        self.history_detail_text.delete("1.0", END)
        self.history_detail_text.insert("1.0", str(values[2]))
        self.history_detail_text.configure(state="disabled")

    def _clear_history(self, parent: Toplevel | None) -> None:
        if not self.history:
            return
        if not messagebox.askyesno("清空历史", "确定要删除全部消息历史吗？", parent=parent):
            return
        self.history.clear()
        save_history(self.history)
        for item in self.activity.get_children():
            self.activity.delete(item)
        self.messages_card.value_var.set("0")  # type: ignore[attr-defined]
        self._refresh_history_view()

    def _refresh_activity(self) -> None:
        for item in self.activity.get_children():
            self.activity.delete(item)
        for t, title, body in self.history[:12]:
            self.activity.insert("", END, values=(t, f"{title}  {body[:22]}"))
        self.messages_card.value_var.set(str(len(self.history)))  # type: ignore[attr-defined]
        self._refresh_history_view()

    def _setup_tray(self) -> None:
        if not pystray or not Image or not ImageDraw:
            return
        icon_image = Image.new("RGBA", (64, 64), "#26a6d1")
        draw = ImageDraw.Draw(icon_image)
        draw.ellipse((5, 5, 59, 59), fill="#26a6d1")
        draw.polygon([(32, 14), (37, 27), (50, 32), (37, 37), (32, 50), (27, 37), (14, 32), (27, 27)], fill="white")
        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", lambda icon, item: self.events.put(("command", "restore", "")), default=True),
            pystray.MenuItem("退出程序", lambda icon, item: self.events.put(("command", "exit", ""))),
        )
        self.tray_icon = pystray.Icon("XundaNotify", icon_image, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _prepare_toast_icons(self) -> dict[str, Path]:
        """Create recognizable platform icons for Windows notification cards."""
        if not Image or not ImageDraw:
            return {}
        try:
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            paths: dict[str, Path] = {}

            def save(platform: str, painter) -> None:
                path = ICON_DIR / f"{PLATFORM_ICON_KEYS[platform]}_v2.png"
                if platform == "QQ":
                    path.write_bytes(QQ_ICON_PNG)
                else:
                    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                    painter(ImageDraw.Draw(image))
                    image.save(path, "PNG")
                paths[platform] = path.resolve()

            def wechat(draw) -> None:
                draw.ellipse((8, 16, 66, 66), fill="#20c65a")
                draw.polygon([(21, 58), (16, 75), (37, 63)], fill="#20c65a")
                draw.ellipse((40, 39, 88, 80), fill="#79df6d")
                draw.polygon([(72, 74), (82, 88), (80, 69)], fill="#79df6d")
                for x in (27, 47):
                    draw.ellipse((x, 36, x + 6, 42), fill="white")
                for x in (56, 73):
                    draw.ellipse((x, 55, x + 5, 60), fill="white")

            def qq(draw) -> None:
                draw.ellipse((22, 6, 74, 66), fill="#161b22")
                draw.ellipse((30, 19, 66, 60), fill="white")
                draw.ellipse((27, 17, 40, 34), fill="white")
                draw.ellipse((56, 17, 69, 34), fill="white")
                draw.ellipse((32, 22, 37, 29), fill="#161b22")
                draw.ellipse((59, 22, 64, 29), fill="#161b22")
                draw.polygon([(40, 34), (56, 34), (48, 43)], fill="#f2b134")
                draw.ellipse((19, 51, 77, 88), fill="#168eea")
                draw.ellipse((33, 58, 63, 84), fill="white")
                draw.ellipse((13, 65, 29, 83), fill="#f4a024")
                draw.ellipse((67, 65, 83, 83), fill="#f4a024")

            def tim(draw) -> None:
                draw.ellipse((7, 7, 89, 89), fill="#3278dd")
                draw.ellipse((25, 23, 71, 66), outline="white", width=7)
                draw.line((48, 30, 48, 74), fill="white", width=8)
                draw.line((31, 35, 65, 35), fill="white", width=7)

            def wecom(draw) -> None:
                draw.ellipse((8, 17, 62, 67), fill="#2d7ff9")
                draw.polygon([(19, 60), (15, 77), (35, 65)], fill="#2d7ff9")
                draw.ellipse((38, 35, 88, 80), fill="#19c68b")
                draw.polygon([(72, 73), (83, 88), (79, 68)], fill="#19c68b")
                for x in (26, 43, 55, 70):
                    y = 37 if x < 50 else 54
                    draw.ellipse((x, y, x + 5, y + 5), fill="white")

            def dingtalk(draw) -> None:
                draw.ellipse((7, 7, 89, 89), fill="#2388f5")
                draw.polygon([(24, 30), (69, 20), (55, 42), (72, 44), (35, 78), (44, 51), (25, 47)], fill="white")

            def feishu(draw) -> None:
                draw.ellipse((7, 7, 89, 89), fill="#3370ff")
                draw.polygon([(24, 28), (47, 17), (62, 31), (39, 43)], fill="white")
                draw.polygon([(39, 45), (64, 31), (75, 50), (50, 64)], fill="#35d4c7")
                draw.polygon([(25, 49), (48, 64), (39, 78), (20, 62)], fill="#ffc53d")

            def whatsapp(draw) -> None:
                draw.ellipse((7, 7, 89, 89), fill="#24cf63")
                draw.ellipse((20, 19, 76, 74), outline="white", width=6)
                draw.polygon([(24, 66), (18, 83), (37, 74)], fill="white")
                draw.arc((31, 28, 66, 64), 120, 325, fill="white", width=7)

            def telegram(draw) -> None:
                draw.ellipse((7, 7, 89, 89), fill="#299bd6")
                draw.polygon([(18, 45), (78, 21), (65, 76), (45, 59), (34, 70), (36, 55)], fill="white")
                draw.line((37, 55, 66, 32), fill="#b7dceb", width=3)

            def weibo(draw) -> None:
                draw.ellipse((8, 17, 77, 84), fill="#e9423a")
                draw.ellipse((22, 35, 68, 72), fill="white")
                draw.ellipse((34, 45, 58, 66), fill="#17191c")
                draw.ellipse((40, 49, 48, 57), fill="white")
                draw.arc((47, 5, 88, 46), 195, 325, fill="#f4a21f", width=7)
                draw.arc((56, 14, 83, 41), 195, 325, fill="#f4a21f", width=6)

            def sms(draw) -> None:
                draw.rounded_rectangle((9, 13, 87, 75), radius=22, fill="#39c568")
                draw.polygon([(24, 68), (17, 87), (42, 73)], fill="#39c568")
                for x in (28, 45, 62):
                    draw.ellipse((x, 41, x + 7, 48), fill="white")

            def gmail(draw) -> None:
                draw.rounded_rectangle((7, 18, 89, 78), radius=10, fill="white", outline="#dadce0", width=2)
                draw.line((12, 24, 48, 53, 84, 24), fill="#ea4335", width=9)
                draw.line((12, 27, 12, 72), fill="#c5221f", width=7)
                draw.line((84, 27, 84, 72), fill="#fbbc04", width=7)

            def xunda(draw) -> None:
                draw.ellipse((7, 7, 89, 89), fill="#26a6d1")
                draw.polygon([(48, 16), (56, 39), (80, 48), (56, 56), (48, 80), (40, 56), (16, 48), (40, 39)], fill="white")

            painters = {
                "微信": wechat, "QQ": qq, "TIM": tim, "企业微信": wecom,
                "钉钉": dingtalk, "飞书": feishu, "WhatsApp": whatsapp,
                "Telegram": telegram, "微博": weibo, "短信": sms,
                "Gmail": gmail, "讯达": xunda,
            }
            for platform, painter in painters.items():
                save(platform, painter)
            LOGGER.info("平台通知图标已就绪：%s", "、".join(paths))
            return paths
        except Exception:
            LOGGER.exception("生成平台通知图标失败")
            return {}

    def _toast_icon_for_title(self, title: str) -> Path | None:
        platform = platform_from_title(title)
        return self.toast_icon_paths.get(platform) or self.toast_icon_paths.get("讯达")

    def _register_windows_toast_app(self) -> None:
        """Register a Start Menu shortcut so Windows keeps Toasts in Action Center."""
        if os.name != "nt":
            return
        try:
            key_path = rf"Software\Classes\AppUserModelId\{TOAST_APP_ID}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(self.toast_icon_path or ""))
                winreg.SetValueEx(key, "IconBackgroundColor", 0, winreg.REG_SZ, "#26A6D1")
            start_menu = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            start_menu.mkdir(parents=True, exist_ok=True)
            shortcut = start_menu / "XundaNotify.lnk"
            target = Path(sys.executable).resolve()
            if getattr(sys, "frozen", False):
                arguments = ""
            else:
                arguments = str(Path(__file__).resolve())
            def ps_quote(value: str) -> str:
                return "'" + value.replace("'", "''") + "'"
            script = (
                "$ws = New-Object -ComObject WScript.Shell; "
                f"$sc = $ws.CreateShortcut({ps_quote(str(shortcut))}); "
                f"$sc.TargetPath = {ps_quote(str(target))}; "
                f"$sc.Arguments = {ps_quote(arguments)}; "
                f"$sc.WorkingDirectory = {ps_quote(str(target.parent))}; "
                f"$sc.IconLocation = {ps_quote(str(target) + ',0')}; "
                f"$sc.Description = {ps_quote(APP_NAME)}; "
                "$sc.Save()"
            )
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=8,
                check=False,
            )
        except Exception:
            # A locked-down machine may deny shortcut registration; the custom popup remains available.
            return

    def _restore_window(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(150, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        LOGGER.info("从系统托盘恢复主窗口")

    def _exit_app(self) -> None:
        self.exit_requested = True
        self._on_close()

    def _open_settings(self) -> None:
        self._show_view("settings")

    def _build_settings_view(self) -> None:
        self.settings_view = Frame(self.main, bg="#0f1720")
        header = Frame(self.settings_view, bg="#0f1720")
        header.pack(fill="x", padx=34, pady=(28, 20))
        ttk.Label(header, text="设置", foreground="#f4f8fb", background="#0f1720", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(header, text="管理服务端口、通知方式和免打扰选项。", foreground="#7f96a8", background="#0f1720").pack(anchor="w", pady=(5, 0))
        panel = Frame(self.settings_view, bg="#18232e", highlightthickness=1, highlightbackground="#263746")
        panel.pack(fill="x", padx=34, pady=(0, 28))
        form = Frame(panel, bg="#18232e")
        form.pack(fill="x", padx=28, pady=24)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="监听端口", foreground="#a9bbc8", background="#18232e").grid(row=0, column=0, sticky="w", pady=12)
        self.settings_port_var = StringVar(value=str(self.config.port))
        Entry(form, textvariable=self.settings_port_var, width=18, bg="#223242", fg="white", insertbackground="white", relief="flat").grid(row=0, column=1, sticky="e", pady=12, ipady=7)
        ttk.Label(form, text="应用名称", foreground="#a9bbc8", background="#18232e").grid(row=1, column=0, sticky="w", pady=12)
        self.settings_name_var = StringVar(value=self.config.app_id)
        Entry(form, textvariable=self.settings_name_var, width=24, bg="#223242", fg="white", insertbackground="white", relief="flat").grid(row=1, column=1, sticky="e", pady=12, ipady=7)
        self.settings_sound_var = BooleanVar(value=self.config.sound)
        self.settings_quiet_var = BooleanVar(value=self.config.quiet_mode)
        ttk.Label(form, text="通知方式", foreground="#a9bbc8", background="#18232e").grid(row=2, column=0, sticky="w", pady=12)
        mode_labels = {
            "Windows 通知": "windows",
            "软件通知": "software",
            "同时通知": "both",
        }
        self.notification_mode_labels = mode_labels
        current_label = next((label for label, value in mode_labels.items() if value == self.config.notification_mode), "同时通知")
        self.settings_mode_var = StringVar(value=current_label)
        ttk.Combobox(form, textvariable=self.settings_mode_var, values=list(mode_labels), state="readonly", width=21).grid(row=2, column=1, sticky="e", pady=12)
        ttk.Checkbutton(form, text="播放通知提示音", variable=self.settings_sound_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Checkbutton(form, text="免打扰模式（仅记录，不弹窗）", variable=self.settings_quiet_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=10)
        ttk.Button(form, text="保存设置", command=self._save_settings, style="Accent.TButton").grid(row=5, column=1, sticky="e", pady=(22, 0))

    def _save_settings(self) -> None:
        try:
            port = int(self.settings_port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror("端口无效", "请输入 1 - 65535 之间的端口。", parent=self.root)
            return
        old_port = self.config.port
        self.config.port = port
        self.config.app_id = self.settings_name_var.get().strip() or APP_NAME
        self.config.sound = self.settings_sound_var.get()
        self.config.quiet_mode = self.settings_quiet_var.get()
        self.config.notification_mode = self.notification_mode_labels.get(self.settings_mode_var.get(), "both")
        save_config(self.config)
        self.address_var.set(f"http://{self.ip}:{self.config.port}/?msg=")
        self.address_card.value_var.set(f"{self.ip}:{self.config.port}")  # type: ignore[attr-defined]
        LOGGER.info("设置已保存：端口=%s，通知方式=%s，免打扰=%s", port, self.config.notification_mode, self.config.quiet_mode)
        if self.running and old_port != port:
            self.stop_server()
            self.start_server()
        self.status_pill.configure(text="●  设置已保存", foreground="#69d6ae")

    def _build_log_view(self) -> None:
        self.log_view = Frame(self.main, bg="#0f1720")
        header = Frame(self.log_view, bg="#0f1720")
        header.pack(fill="x", padx=34, pady=(28, 20))
        ttk.Label(header, text="运行日志", foreground="#f4f8fb", background="#0f1720", font=("Segoe UI", 24, "bold")).pack(side="left")
        ttk.Label(header, text="●  实时更新", foreground="#69d6ae", background="#0f1720", font=("Segoe UI", 9, "bold")).pack(side="right", padx=(0, 10))
        ttk.Button(header, text="刷新", command=self._refresh_log_view, style="Ghost.TButton").pack(side="right")
        panel = Frame(self.log_view, bg="#18232e", highlightthickness=1, highlightbackground="#263746")
        panel.pack(fill="both", expand=True, padx=34, pady=(0, 28))
        log_box = Frame(panel, bg="#111c27")
        log_box.pack(fill="both", expand=True, padx=14, pady=14)
        log_scroll_y = ttk.Scrollbar(log_box, orient="vertical")
        log_scroll_x = ttk.Scrollbar(log_box, orient="horizontal")
        self.log_text = Text(
            log_box,
            bg="#111c27",
            fg="#c8d8e4",
            insertbackground="white",
            relief="flat",
            wrap="none",
            font=("Consolas", 9),
            yscrollcommand=log_scroll_y.set,
            xscrollcommand=log_scroll_x.set,
        )
        log_scroll_y.configure(command=self.log_text.yview)
        log_scroll_x.configure(command=self.log_text.xview)
        log_scroll_y.pack(side="right", fill="y")
        log_scroll_x.pack(side="bottom", fill="x")
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _log_files(self) -> list[Path]:
        files = [LOG_FILE.with_name(f"{LOG_FILE.name}.{index}") for index in range(3, 0, -1)]
        files.append(LOG_FILE)
        return [path for path in files if path.exists()]

    def _log_signature(self) -> tuple[tuple[str, int, int], ...]:
        signature = []
        for path in self._log_files():
            try:
                stat = path.stat()
                signature.append((path.name, stat.st_mtime_ns, stat.st_size))
            except OSError:
                continue
        return tuple(signature)

    def _refresh_log_view(self, force_scroll: bool = True) -> None:
        if not self.log_text:
            return
        current_view = self.log_text.yview()
        at_bottom = not current_view or current_view[1] >= 0.995
        try:
            chunks = [path.read_text(encoding="utf-8", errors="replace") for path in self._log_files()]
            content = "".join(chunks) or "暂无运行日志"
            self.log_file_signature = self._log_signature()
        except Exception:
            content = "暂无运行日志"
            self.log_file_signature = ()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", END)
        self.log_text.insert("1.0", content)
        if force_scroll or at_bottom:
            self.log_text.see(END)
        elif current_view:
            self.log_text.yview_moveto(current_view[0])
        self.log_text.configure(state="disabled")

    def _poll_log_file(self) -> None:
        signature = self._log_signature()
        if signature != self.log_file_signature:
            self._refresh_log_view(force_scroll=False)
        self.root.after(500, self._poll_log_file)

    def copy_address(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.address_var.get())
        self.root.update()
        self.status_pill.configure(text="●  地址已复制", foreground="#69d6ae")

    def send_test(self) -> None:
        self.events.put(("message", "测试通知", "讯达通知中心运行正常，欢迎使用。"))

    def toggle_server(self) -> None:
        if self.running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self) -> None:
        if self.running:
            return
        try:
            self.server = ThreadingHTTPServer(("0.0.0.0", self.config.port), NotifyHandler)
            self.server.app = self  # type: ignore[attr-defined]
        except OSError as exc:
            LOGGER.exception("服务启动失败：端口=%s", self.config.port)
            messagebox.showerror("无法启动服务", f"端口 {self.config.port} 可能已被占用。\n{exc}")
            return
        self.running = True
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.toggle_button.configure(text="停止服务")
        self.server_card.value_var.set("运行中")  # type: ignore[attr-defined]
        self.server_card.winfo_children()[0].configure(bg="#59d39c")
        self.status_pill.configure(text="●  服务运行中", foreground="#69d6ae")
        LOGGER.info("WebHook 服务已启动：http://%s:%s/", self.ip, self.config.port)

    def stop_server(self) -> None:
        was_running = self.running
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.server = None
        self.running = False
        self.toggle_button.configure(text="启动服务")
        self.server_card.value_var.set("未启动")  # type: ignore[attr-defined]
        self.server_card.winfo_children()[0].configure(bg="#f0a35e")
        self.status_pill.configure(text="●  服务未启动", foreground="#ffb36b")
        if was_running:
            LOGGER.info("WebHook 服务已停止")

    def _show_notification(self, title: str, body: str, received_at: str) -> None:
        if self.config.quiet_mode:
            LOGGER.info("免打扰模式：通知仅记入历史，标题=%s", title)
            return
        mode = self.config.notification_mode
        display_body = notification_body(body)
        if mode in ("software", "both"):
            self._show_popup(title, display_body, received_at)
            LOGGER.info("软件通知已显示：标题=%s", title)
            if self.config.sound and mode == "software":
                self.root.bell()
        if mode in ("windows", "both") and Notification:
            try:
                toast_icon = self._toast_icon_for_title(title)
                # Keep the AppUserModelID ASCII: winotify/WinRT rejects CJK app IDs.
                toast = Notification(
                    app_id=TOAST_APP_ID,
                    title=clean_title(title),
                    msg=f"{display_body}\n接收时间 {received_at}",
                    icon=toast_icon.as_uri() if toast_icon else "",
                    duration="long",
                )
                if self.config.sound and audio:
                    toast.set_audio(audio.Default, loop=False)
                toast.show()
                LOGGER.info("Windows 通知已发送：平台=%s，标题=%s", platform_from_title(title), title)
                return
            except Exception:
                LOGGER.exception("Windows 通知发送失败：标题=%s", title)
                fallback = "，已显示软件通知" if mode == "both" else ""
                self.status_pill.configure(text=f"●  Windows 通知发送失败{fallback}", foreground="#ffb36b")
        elif mode == "windows":
            LOGGER.error("Windows 通知组件不可用")
            self.status_pill.configure(text="●  Windows 通知组件不可用", foreground="#ffb36b")

    def _show_popup(self, title: str, body: str, received_at: str) -> None:
        popup = Toplevel(self.root)
        self.popups.append(popup)
        popup.title(title)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#1b2a38")
        width, height = 390, 132
        x = popup.winfo_screenwidth() - width - 24
        y = popup.winfo_screenheight() - height - 64 - (len(self.popups) - 1) * (height + 10)
        popup.geometry(f"{width}x{height}+{x}+{max(20, y)}")
        Frame(popup, bg="#39b8d5", width=5).pack(side="left", fill="y")
        content = Frame(popup, bg="#1b2a38")
        content.pack(side="left", fill="both", expand=True, padx=16, pady=13)
        top = Frame(content, bg="#1b2a38")
        top.pack(fill="x")
        ttk.Label(top, text=f"接收时间 {received_at}", foreground="#70d69a", background="#1b2a38", font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(top, text="×", width=3, command=lambda: self._close_popup(popup), style="Ghost.TButton").pack(side="right")
        ttk.Label(content, text=clean_title(title), foreground="#f6fbff", background="#1b2a38", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(7, 1))
        ttk.Label(content, text=clean_body(body)[:120], foreground="#c1d2df", background="#1b2a38", wraplength=330, justify="left", font=("Segoe UI", 10)).pack(anchor="w")
        popup.after(7000, lambda: self._close_popup(popup))

    def _close_popup(self, popup: Toplevel) -> None:
        if popup in self.popups:
            self.popups.remove(popup)
        if popup.winfo_exists():
            popup.destroy()

    def _poll_events(self) -> None:
        try:
            while True:
                kind, title, body = self.events.get_nowait()
                if kind == "message":
                    now = time.strftime("%H:%M:%S")
                    self.history.insert(0, (now, title, body))
                    self.history = self.history[:500]
                    save_history(self.history)
                    self.activity.insert("", 0, values=(now, f"{title}  {body[:22]}"))
                    if len(self.activity.get_children()) > 12:
                        self.activity.delete(self.activity.get_children()[-1])
                    self.messages_card.value_var.set(str(len(self.history)))  # type: ignore[attr-defined]
                    self._refresh_history_view()
                    self._show_notification(title, body, now)
                elif kind == "command":
                    if title == "restore":
                        self._restore_window()
                    elif title == "exit":
                        self._exit_app()
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    def _on_close(self) -> None:
        if not self.exit_requested:
            self.root.withdraw()
            LOGGER.info("主窗口已隐藏，程序继续在系统托盘运行")
            return
        LOGGER.info("正在退出应用")
        self.stop_server()
        if self.tray_icon:
            self.tray_icon.stop()
        try:
            for handler in LOGGER.handlers:
                handler.flush()
            LOG_FILE.write_text("", encoding="utf-8")
        except Exception:
            LOGGER.exception("退出时清理运行日志失败")
        self.root.destroy()


def main() -> None:
    root = Tk()
    app = NotifyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
