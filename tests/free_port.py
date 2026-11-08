"""Claim a free local port for one test run, from 8799 upward and never 8765 (the live page).

Two agents run tests/smoke.sh and tests/replay_all.py on this laptop; a fixed port made their runs collide. The claim
is a lock directory /tmp/oxn_test_port_<port> (mkdir is atomic) plus a bind check; the caller removes it with
release(), and a lock older than 30 minutes counts as stale.

    PORT=$(.venv/bin/python tests/free_port.py)      # prints the claimed port
"""
import os
import socket
import time

LOCK = "/tmp/oxn_test_port_{}"
LIVE_PORT = 8765


def claim(start=8799, stop=8830):
    for p in range(start, stop):
        if p == LIVE_PORT:
            continue
        d = LOCK.format(p)
        try:
            if os.path.isdir(d) and time.time() - os.path.getmtime(d) > 1800:
                os.rmdir(d)
            os.mkdir(d)
        except OSError:
            continue                                   # another run holds this port
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", p))
            return p
        except OSError:
            os.rmdir(d)                                # something else listens here
        finally:
            s.close()
    raise SystemExit(f"no free test port between {start} and {stop - 1}")


def release(p):
    try:
        os.rmdir(LOCK.format(p))
    except OSError:
        pass


if __name__ == "__main__":
    print(claim())
