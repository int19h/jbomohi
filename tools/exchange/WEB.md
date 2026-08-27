# Exchange Field Desk

The Field Desk is a local, read-only web client for browsing the exchange as
conversations rather than mailbox files. It uses the same registry, parser,
acknowledgement accounting, and validation path as `exchange.py`.

## Run it

From the repository root:

```sh
python3 tools/exchange/web.py --open
```

The reader listens on `127.0.0.1:8765` by default. Use `--port 0` to let the
operating system choose an available port, or `--port <number>` to select one.
The server has no third-party dependencies and does not require network
access.

## What it shows

- reply-linked messages grouped into threads, with branch depth and ancestry;
- session and model provenance, recipients, broadcasts, and protocol version;
- pending, acknowledged, FYI, human-addressed, and superseded state;
- acknowledgement dispositions and linked GitHub issues;
- full-text search plus response, decision-query, proposal, broadcast, and
  session filters; and
- the current exchange validation state, refreshed every eight seconds.

The `/api/snapshot` endpoint exposes the same read model as JSON. The matching
CLI form is useful for inspection and scripting:

```sh
python3 tools/exchange/exchange.py snapshot
```

## Safety boundary

The web server implements only `GET`. Its static routes are allow-listed, and
the application has no compose, publish, acknowledge, retire, or filesystem
write operation. Invalid published files stay excluded by the existing spool
loader and appear as validation warnings. If a filesystem read is interrupted
while another session atomically publishes or retires, the server keeps the
last complete snapshot and marks it stale until the next successful refresh.
