import queue
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class Dummy:
    events = queue.Queue()


dummy = Dummy()
server = ThreadingHTTPServer(("127.0.0.1", 0), app.NotifyHandler)
server.app = dummy
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
url = "http://127.0.0.1:%d/?msg=%%5B%%E5%%BE%%AE%%E4%%BF%%A1%%5D%%E5%%B0%%8F%%E6%%98%%8E%%3A%%E4%%BD%%A0%%E5%%A5%%BD" % server.server_port
print(urllib.request.urlopen(url).read().decode("utf-8"))
print(dummy.events.get_nowait())
server.shutdown()
server.server_close()
