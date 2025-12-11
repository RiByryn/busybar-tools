import socket
import sys
import termios
import tty
import select

# socat alternative: socat STDIO,raw,echo=0,opost=1,onlcr=1,escape=0x1d TCP:10.0.4.20:23,crnl

ESCAPE_BYTE = b'\x1d'  # Ctrl+] to exit

def run_session(host: str, port: int, tcp_timeout: int) -> None:
    # Save original tty settings
    fd = sys.stdin.fileno()
    orig_attrs = termios.tcgetattr(fd)

    try:
        # Make stdin "raw" but keep output processing (opost/onlcr)
        attrs = termios.tcgetattr(fd)
        # lflag: disable canonical mode, echo and signals
        lflag = attrs[3]
        lflag &= ~termios.ICANON
        lflag &= ~termios.ECHO
        lflag &= ~termios.ISIG
        attrs[3] = lflag
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)

        # Connect TCP
        sock = socket.create_connection((host, port), timeout=tcp_timeout)

        # Main loop
        while True:
            rlist, _, _ = select.select([sys.stdin, sock], [], [])

            # Data from stdin
            if sys.stdin in rlist:
                data = sys.stdin.buffer.read(1)
                if not data:
                    # EOF on stdin
                    break

                if data == ESCAPE_BYTE:
                    # Local escape: close connection and exit
                    break

                # Translate '\n' to '\r\n' like crnl
                if data == b'\n':
                    sock.sendall(b'\r\n')
                else:
                    sock.sendall(data)

            # Data from socket
            if sock in rlist:
                data = sock.recv(4096)
                if not data:
                    # Connection closed
                    break
                # Just write to stdout as-is
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()

        sock.close()

    finally:
        # Restore terminal attributes
        termios.tcsetattr(fd, termios.TCSADRAIN, orig_attrs)


# if __name__ == "__main__":
#     run_session("10.0.4.20", 23)
