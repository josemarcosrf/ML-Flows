import json
import threading
import time

import click
import redis
from loguru import logger

from flows.settings import settings


class RedisPubSubClient:
    def __init__(
        self,
        host: str = settings.REDIS_HOST,
        port: int = settings.REDIS_PORT,
        db: int = 0,
        password: str | None = None,
        use_ssl: bool = True,
    ):
        """Initialize Redis connection parameters (but don't connect yet).

        Args:
            host (str): Redis server hostname
            port (int): Redis server port
            db (int): Redis database number
            password (str, optional): Redis password if authentication is required
        """
        # Store connection parameters instead of creating connections immediately
        pwd = (
            password or settings.REDIS_PWD.get_secret_value()
            if settings.REDIS_PWD
            else None
        )
        self.connection_params = {
            "host": host,
            "port": port,
            "db": db,
            "password": pwd,
            "decode_responses": True,
            "ssl": use_ssl,
        }
        # These will be initialized when needed
        self._client = None
        self._pubsub = None
        self._subscribers = {}
        self._listener_thread = None
        self._running = False

    @property
    def client(self):
        """Lazy initialization of Redis client."""
        if self._client is None:
            print(f"🔗 Connecting to Redis server {self.connection_params['host']}")
            self._client = redis.Redis(**self.connection_params)
        return self._client

    @property
    def pubsub(self):
        """Lazy initialization of PubSub object."""
        if self._pubsub is None:
            self._pubsub = self.client.pubsub()
        return self._pubsub

    def publish(self, channel: str, message: dict | str) -> int:
        """Publish a message to a channel.

        Args:
            channel (str): The channel to publish to
            message (dict or str): The message to publish

        Returns:
            int: Number of clients that received the message
        """
        if isinstance(message, dict):
            message = json.dumps(message)
        return self.client.publish(channel, message)

    def subscribe(self, channel: str, callback: callable):
        """Subscribe to a channel.

        Args:
            channel (str): The channel to subscribe to
            callback (callable): Function to call when a message is received
        """
        self._subscribers[channel] = callback

        if "*" in channel:
            self.pubsub.psubscribe(**{channel: self._message_handler})
        else:
            self.pubsub.subscribe(**{channel: self._message_handler})

        # Start the listener thread if not already running
        if not self._running:
            self._start_listener()

    def unsubscribe(self, channel: str):
        """Unsubscribe from a channel.

        Args:
            channel (str): The channel to unsubscribe from
        """
        if channel in self._subscribers:
            if "*" in channel:
                self.pubsub.punsubscribe(channel)
            else:
                self.pubsub.unsubscribe(channel)
            del self._subscribers[channel]

    def _message_handler(self, message):
        """Handle incoming messages and route to appropriate callbacks.

        Args:
            message (dict): Redis message
        """
        channel = message.get("channel")
        pattern = message.get("pattern")
        data = message.get("data")

        # Skip subscription confirmation messages
        if data == 1 or data == "subscribe" or data == "psubscribe":
            return

        # Try to parse JSON data
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            pass

        # Route to the appropriate callback
        if pattern and pattern in self._subscribers:
            self._subscribers[pattern](channel, data)
        elif channel and channel in self._subscribers:
            self._subscribers[channel](data)

    def _start_listener(self):
        """Start the listener thread."""
        self._running = True
        self._listener_thread = threading.Thread(target=self._listen)
        self._listener_thread.daemon = True
        self._listener_thread.start()

    def _listen(self):
        """Listen for messages in a separate thread."""
        while self._running:
            try:
                message = self.pubsub.get_message()
                if message:
                    self._message_handler(message)
                time.sleep(0.001)  # Small sleep to prevent CPU hogging
            except Exception as e:
                logger.error(f"Error in listener thread: {e}")
                time.sleep(1)  # Sleep longer on error

    def close(self):
        """Close connections and stop the listener thread."""
        self._running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=1.0)
        if self._pubsub:
            self._pubsub.close()
        if self._client:
            self._client.close()
        self._client = None
        self._pubsub = None
        self._listener_thread = None

    def __getstate__(self):
        """Custom pickling behavior to exclude unpicklable objects."""
        state = self.__dict__.copy()
        # Remove unpicklable objects
        state["_client"] = None
        state["_pubsub"] = None
        state["_client"] = None
        state["_pubsub"] = None
        state["_running"] = False
        state["_listener_thread"] = None
        return state

    def __setstate__(self, state):
        """Custom unpickling behavior to restore the object state."""
        self.__dict__.update(state)


class UpdatePublisher(RedisPubSubClient):
    """Very thin wrapper around RedisPubSubClient to publish updates for a given
    client and document.
    """

    def __init__(
        self,
        client_id: str,
        host: str = settings.REDIS_HOST,
        port: int = settings.REDIS_PORT,
        db: int = 0,
        password: str | None = None,
    ):
        """Initialize the UpdatePublisher."""
        password = password or (
            settings.REDIS_PWD.get_secret_value() if settings.REDIS_PWD else None
        )

        super().__init__(host, port, db, password)
        self.client_id = client_id

    def publish_update(
        self, message: str, doc_id: str | None = None, **extra_fields
    ) -> int:
        # Construct the channel name based on client_id, project_id, and doc_id
        # Possible channels:
        #   - client_id/updates
        #   - client_id/project:<project_id>/updates
        #   - client_id/project:<project_id>/doc:<doc_id>/updates
        channel = f"{self.client_id}/"
        if "project_id" in extra_fields:
            channel += f"project:{extra_fields['project_id']}/"
        if doc_id:
            channel += f"doc:{doc_id}/"
        channel += "updates"

        try:
            payload = {"message": message, **extra_fields}
            logger.debug(f"📨 Publishing update for channel {channel}: {payload}")
            return self.publish(channel, payload)
        except Exception as e:
            logger.warning(f"🙇 Error publishing update for channel {channel}: {e}")
            return 0


@click.group()
@click.option(
    "--host",
    default=settings.REDIS_HOST,
    help="Redis server hostname",
)
@click.option(
    "--port",
    default=settings.REDIS_PORT,
    type=int,
    help="Redis server port",
)
@click.option(
    "--db",
    default=0,
    type=int,
    help="Redis database number",
)
@click.option(
    "--password",
    default=None,
    help="Redis password if authentication is required",
)
@click.option(
    "--use-ssl",
    is_flag=True,
    default=False,
    help="Use SSL for Redis connection",
)
@click.pass_context
def cli(ctx, host, port, db, password, use_ssl):
    """CLI for Redis PubSub Client."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = RedisPubSubClient(host, port, db, password, use_ssl)


@cli.command("pub")
@click.option(
    "--channel",
    required=True,
    help="Channel to publish to",
)
@click.option(
    "--message",
    required=True,
    help="Message to publish (JSON string)",
)
@click.pass_context
def publish(ctx, channel, message):
    """Publish a message to a channel."""
    client = ctx.obj["client"]
    try:
        message = json.loads(message)
    except json.JSONDecodeError:
        pass
    client.publish(channel, message)
    logger.info(f"📬 Published message to {channel}: {message}")


@cli.command("sub")
@click.option(
    "--channel",
    required=True,
    help="Channel to subscribe to",
)
@click.pass_context
def subscribe(ctx, channel):
    """Subscribe to a channel."""
    client = ctx.obj["client"]

    def callback(message):
        logger.info(f"📥 Received message on {channel}: {message}")

    client.subscribe(channel, callback)
    logger.info(f"📬 Subscribed to {channel}. Waiting for messages...")

    try:
        s = 0
        while True:
            print(f"Listening for messages... {s}", end="\r", flush=True)
            time.sleep(1)
            s += 1
    except KeyboardInterrupt:
        client.unsubscribe(channel)
        logger.info(f"📭 Unsubscribed from {channel}.")


if __name__ == "__main__":
    cli()
