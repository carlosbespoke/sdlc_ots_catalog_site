import json

from kombu import Connection, Exchange, Queue
from kombu.simple import SimpleQueue

CASES = [("latin-1", "text/plain", "Säure, Öl & Maß"), ("utf-16", "text/plain", "Grüße aus Köln"),
         ("shift_jis", "text/csv", "東京,大阪,名古屋"), ("ISO-8859-15", "text/plain", "€ œ Ž"),
         ("koi8-r", "text/plain", "Привет")]


def observe():
    obs = {"producer": {}, "simple": {}, "default": None}
    exchange = Exchange("charsets.p2", "direct")
    queue = Queue("charsets.p2", exchange, "c")
    with Connection("memory://") as conn:
        channel = conn.default_channel
        producer = conn.Producer(channel)
        for encoding, ctype, text in CASES:
            producer.publish(text, exchange=exchange, routing_key="c", declare=[queue],
                             content_type=ctype, content_encoding=encoding)
            message = queue(channel).get(no_ack=True)
            obs["producer"][encoding] = [message.content_encoding, message.body.hex()]
        producer.publish("Grüße", exchange=exchange, routing_key="c", declare=[queue],
                         content_type="text/plain")
        message = queue(channel).get(no_ack=True)
        obs["default"] = [message.content_encoding, message.body.hex()]
        simple = SimpleQueue(channel, "charsets.p2.simple")
        for encoding, ctype, text in CASES:
            simple.put(text, content_type=ctype, content_encoding=encoding)
            message = simple.get(block=False)
            message.ack()
            obs["simple"][encoding] = message.body.hex()
        simple.close()
    return obs


try:
    result = observe()
except Exception as error:  # observations only
    result = {"error": type(error).__name__}
print(json.dumps(result, sort_keys=True))
