# pyaduct

Sometimes all you need is duct tape. `pyaduct` is a messaging bus that 
can create a bridge between your Python classes, whether they are 
running on the same system (IPC), or distributed across multiple 
machines (TCP/IP).

Stand up the Broker, inject Clients, and your classes can communicate
seamlessly - locally or over the wire.

# Installation

`pip install pyaduct`

# The Abstraction

`pydduct` provides two main classes - the Broker and Client. A Broker can
be be bound to a IPC or TCP/IP socket, and is the central message router
for the system. Any number of Clients can be connected to the Broker,
and these clients expose two primary message patterns:

- Request/Response
- Publish/Subscribe

Using the ZeroMQ DEALER and ROUTER sockets under the hood, `pyaduct`
supports a fully asynchonrous messaging model.

# Examples

See the `examples/` for more details on how to integrate the Broker
and Client into an actor based messaging system.

Or run `pyaduct demo` to see a live demo of the nodes coming online,
sending various messages, events, and pings, and cleanly shutting down.

# Convenient

There are other conveience methods exposed by Clients to help them
communicate with one another -

- Get a complete list of clients from the broker
- Ping other clients

# Message Store

Boasting UUID7 IDs for global message ordering, `pyaduct` also supports
a simple in-memory message store for now, with support for a `sqlite`
backend coming soon.

# Production?

Is `pyaduct` fault tolerant? Resilent to network failures? Contains
complicated leader consensus mechanisms? None of the above! `pyaduct`
proudly supports a single point of failure (namely, the Broker). Use in
production at your own risk.

`pyaduct` is changing fast; expect breaking changes as as the
implementation stabilizes and approaches 1.0.

However, it is great for standing up a proof of concept which could
later be implemented with a more robust system such as Kafka.

# Demo

```bash
❯ pyaduct demo
Timestamp: 2025-04-01 01:11:25.862587+00:00
Client 1 subscribed to test_topic
Client 2 generated event: id=UUID('067eb3d3-f5fc-7a31-8000-1791d1d000f2') type=<MessageType.EVENT: 'EVENT'> timestamp=datetime.datetime(2025, 4, 1, 1, 11, 27, 374193,
tzinfo=datetime.timezone.utc) source='client_2' body='hello world' topic='test_topic'
{
  "id": "067eb3d3-f5fc-7a31-8000-1791d1d000f2",
  "type": "EVENT",
  "timestamp": "2025-04-01T01:11:27.374193Z",
  "source": "client_2",
  "body": "hello world",
  "topic": "test_topic"
}
Client 1 received event: id=UUID('067eb3d3-f5fc-7a31-8000-1791d1d000f2') type=<MessageType.EVENT: 'EVENT'> timestamp=datetime.datetime(2025, 4, 1, 1, 11, 27, 374193, tzinfo=TzInfo(UTC))
source='client_2' body='hello world' topic='test_topic'
Client 1 pinged Client 2 successfully
⠋ Shutting down...
                                                 broker Messages
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Message ID                           ┃ Direction ┃ Type      ┃ Body        ┃ Timestamp                        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 067eb3d3-ddf2-7e9c-8000-30db67ee7cd1 │ RX        │ REGISTER  │ REGISTER    │ 2025-04-01 01:11:25.871870+00:00 │
│ 067eb3d3-df31-7a5c-8000-46ef8674eb7f │ TX        │ ACK       │ ACK         │ 2025-04-01 01:11:25.962198+00:00 │
│ 067eb3d3-ebd1-7cc1-8000-18b44eecff10 │ RX        │ REGISTER  │ REGISTER    │ 2025-04-01 01:11:26.739001+00:00 │
│ 067eb3d3-ec9e-78b3-8000-8b29c6f65ece │ TX        │ ACK       │ ACK         │ 2025-04-01 01:11:26.788720+00:00 │
│ 067eb3d3-f562-7fce-8000-3b27a6b7b629 │ RX        │ SUBSCRIBE │ SUBSCRIBE   │ 2025-04-01 01:11:27.336683+00:00 │
│ 067eb3d3-f5fc-7a31-8000-1791d1d000f2 │ RX        │ EVENT     │ hello world │ 2025-04-01 01:11:27.374193+00:00 │
│ 067eb3d3-f64d-7834-8000-041750548e5c │ TX        │ ACK       │ ACK         │ 2025-04-01 01:11:27.412569+00:00 │
│ 067eb3d4-0824-7c1e-8000-044195a83c09 │ RX        │ PING      │ PING        │ 2025-04-01 01:11:28.508987+00:00 │
│ 067eb3d4-1756-7084-8000-aab4169c1e9a │ RX        │ PONG      │ PONG        │ 2025-04-01 01:11:29.458518+00:00 │
└──────────────────────────────────────┴───────────┴───────────┴─────────────┴──────────────────────────────────┘
```
