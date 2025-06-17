from flows.common.clients import pubsub


class DummyCallback:
    def __init__(self):
        self.messages = []

    def __call__(self, *args, **kwargs):
        self.messages.append((args, kwargs))


def test_redis_pubsub_client_publish_and_subscribe(monkeypatch):
    # Mock redis.Redis and its methods
    class DummyRedis:
        def __init__(self, **kwargs):
            self.published = []
            self.subscribed = []
            self.unsubscribed = []

        def publish(self, channel, message):
            self.published.append((channel, message))
            return 1

        def pubsub(self):
            return self

        def subscribe(self, **kwargs):
            self.subscribed.append(kwargs)

        def unsubscribe(self, channel):
            self.unsubscribed.append(channel)

        def psubscribe(self, **kwargs):
            self.subscribed.append(kwargs)

        def punsubscribe(self, channel):
            self.unsubscribed.append(channel)

        def get_message(self):
            return None

        def close(self):
            pass

    monkeypatch.setattr(pubsub.redis, "Redis", DummyRedis)

    # Create a RedisPubSubClient instance
    client = pubsub.RedisPubSubClient(host="localhost", port=6379, db=0, use_ssl=False)

    # Assert that the client is initialized correctly
    assert isinstance(client.client, DummyRedis)

    # Assert that the message was published
    assert client.publish("chan", {"foo": "bar"}) == 1
    cb = DummyCallback()
    client.subscribe("chan", cb)

    # Assert that the callback is registered
    assert client._subscribers["chan"] == cb

    # Unsubscribe from the channel
    client.unsubscribe("chan")
    assert "chan" not in client._subscribers
    client.close()


def test_update_publisher_channel_naming(monkeypatch):
    monkeypatch.setattr(
        pubsub.redis,
        "Redis",
        lambda **kwargs: type(
            "Dummy",
            (),
            {
                "publish": lambda self, c, m: 1,
                "pubsub": lambda self: self,
                "close": lambda self: None,
            },
        )(),
    )
    publisher = pubsub.UpdatePublisher(
        client_id="cid", host="localhost", port=6379, db=0
    )
    # No project_id, no doc_id
    assert publisher.publish_update("msg") == 1
    # With project_id
    assert publisher.publish_update("msg", project_id="pid") == 1
    # With doc_id
    assert publisher.publish_update("msg", doc_id="did") == 1
    # With both
    assert publisher.publish_update("msg", doc_id="did", project_id="pid") == 1


def test_pubsub_getstate_setstate():
    client = pubsub.RedisPubSubClient(host="localhost", port=6379, db=0, use_ssl=False)
    state = client.__getstate__()
    new_client = pubsub.RedisPubSubClient(
        host="localhost", port=6379, db=0, use_ssl=False
    )
    new_client.__setstate__(state)
    assert new_client._client is None
    assert new_client._pubsub is None
    assert new_client._listener_thread is None
