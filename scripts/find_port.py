"""Print the first free TCP port in [8501, 8600) on 127.0.0.1 (used by start scripts)."""
import socket
import sys

start = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
for p in range(start, start + 100):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", p))
        except OSError:
            continue
        print(p)
        break
