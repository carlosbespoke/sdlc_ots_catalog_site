import json

from kombu import Connection
from kombu.serialization import loads
from kombu.simple import SimpleQueue

CASES = [("latin-1", "text/plain", "Säure, Öl & Maß"), ("UTF-16", "text/plain", "Grüße aus Köln"),
         ("shift_jis", "text/csv", "東京,大阪,名古屋"), ("CP1252", "text/plain", "„Zitat“ – €5"),
         ("koi8-r", "application/x-ledger", "Привет")]


def observe():
    obs = {"loads": {}, "consumer": {}}
    for encoding, ctype, text in CASES:
        try:
            obs["loads"][encoding] = loads(text.encode(encoding), ctype, encoding)
        except Exception as error:
            obs["loads"][encoding] = "error:" + type(error).__name__
    with Connection("memory://") as conn:
        simple = SimpleQueue(conn.default_channel, "charsets.p3")
        for encoding, ctype, text in CASES:
            simple.put(text.encode(encoding), content_type=ctype, content_encoding=encoding)
            message = simple.get(block=False)
            message.ack()
            try:
                obs["consumer"][encoding] = message.decode()
            except Exception as error:
                obs["consumer"][encoding] = "error:" + type(error).__name__
        simple.close()
    return obs


try:
    result = observe()
except Exception as error:  # observations only
    result = {"error": type(error).__name__}
print(json.dumps(result, sort_keys=True))
