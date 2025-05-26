import time

import click

from flows.common.clients.pubsub import RedisPubSubClient
from flows.settings import settings


# Define a callback function for pattern subscriptions
def handle_message(*args):
    if len(args) == 2:
        channel, data = args
        print(f"📥 Received message on channel {channel}: {data}")
    else:
        print(f"📥 Received message: {args[0]}")


@click.group("pubsub")
@click.option("--host", default=settings.REDIS_HOST)
@click.option("--port", default=settings.REDIS_PORT)
@click.pass_context
def pubsub_cli(ctx, host, port):
    """Redis PubSub CLI"""
    ctx.ensure_object(dict)
    ctx.obj["client"] = RedisPubSubClient(host, port)


@pubsub_cli.command()
@click.argument("channel", type=str)
@click.pass_context
def sub(ctx, channel):
    client = ctx.obj["client"]
    client.subscribe(channel, handle_message)

    # Keep the program running to receive messages
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.close()
        print("Client closed")


@pubsub_cli.command()
@click.argument("channel", type=str)
@click.argument("message", type=str)
@click.pass_context
def pub(ctx, channel, message):
    client = ctx.obj["client"]
    client.publish(channel, message)
    # Publish a message
    print(f"📤 Published message to channel {channel}: {message}")
