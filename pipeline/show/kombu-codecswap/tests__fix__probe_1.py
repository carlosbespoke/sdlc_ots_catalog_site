import json

from kombu import Connection, Exchange, Queue

ROWS = ["4711;Zoë Brontë;Crème brûlée;€4,50", "4712;Ångström Œuvre;naïve „Fünf“;€12,00"]


def observe():
    obs = {}
    exchange = Exchange("wms.bridge", "direct")
    inbound = Queue("wms.inbound.p1", exchange, "inbound")
    outbound = Queue("wms.outbound.p1", exchange, "outbound")
    with Connection("memory://") as conn:
        channel = conn.default_channel
        producer = conn.Producer(channel)
        # rows as the warehouse system puts them on the queue: already Windows-1252 bytes
        for row in ROWS:
            producer.publish(row.encode("cp1252"), exchange=exchange, routing_key="inbound",
                             declare=[inbound], content_type="text/csv", content_encoding="cp1252")
        # rows our service sends back to the warehouse system
        for row in ROWS:
            producer.publish(row, exchange=exchange, routing_key="outbound",
                             declare=[outbound], content_type="text/csv", content_encoding="cp1252")
        received, wire, roundtrip = [], [], []
        for _ in ROWS:
            message = inbound(channel).get(no_ack=True)
            received.append(message.payload)
        for _ in ROWS:
            message = outbound(channel).get(no_ack=True)
            wire.append(message.body.hex())
            roundtrip.append(message.payload)
        obs["received"] = received
        obs["wire"] = wire
        obs["roundtrip"] = roundtrip
    return obs


try:
    result = observe()
except Exception as error:  # observations only
    result = {"error": type(error).__name__}
print(json.dumps(result, sort_keys=True))
