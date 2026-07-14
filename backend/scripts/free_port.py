import sys
import time

import psutil


def free_port(port: int) -> None:
    """Arrête les processus qui écoutent sur le port indiqué."""

    found = False

    for connection in psutil.net_connections(kind="inet"):
        if not connection.laddr:
            continue

        if connection.laddr.port != port:
            continue

        if connection.status != psutil.CONN_LISTEN:
            continue

        if connection.pid is None:
            continue

        found = True

        try:
            process = psutil.Process(connection.pid)

            print(
                f"Port {port} utilisé par "
                f"{process.name()} (PID {process.pid}). Arrêt..."
            )

            process.terminate()

            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                print("Arrêt normal impossible. Arrêt forcé...")
                process.kill()
                process.wait(timeout=5)

            print(f"Port {port} libéré.")

        except psutil.NoSuchProcess:
            pass

        except psutil.AccessDenied:
            print(
                f"Permission refusée pour arrêter le processus "
                f"sur le port {port}."
            )
            sys.exit(1)

    if not found:
        print(f"Port {port} déjà libre.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Utilisation : python scripts/free_port.py PORT [PORT ...]")
        sys.exit(1)

    for value in sys.argv[1:]:
        try:
            port = int(value)
        except ValueError:
            print(f"Port incorrect : {value}")
            sys.exit(1)

        free_port(port)
        time.sleep(1)


if __name__ == "__main__":
    main()