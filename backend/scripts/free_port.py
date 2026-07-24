import argparse
import sys
import time

import psutil

DEFAULT_ALLOWED_NAMES = {"python", "python.exe", "uvicorn", "uvicorn.exe"}


def free_port(port: int, allowed_names: set[str] | None = None, assume_yes: bool = False) -> None:
    """Stop only an allowed local development process listening on the given port."""

    found = False
    allowed_names = {name.lower() for name in (allowed_names or DEFAULT_ALLOWED_NAMES)}

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
            process_name = process.name().lower()
            if process_name not in allowed_names:
                print(
                    f"Port {port} utilise par {process.name()} (PID {process.pid}). "
                    "Processus non autorise, aucun arret effectue."
                )
                continue

            print(f"Port {port} utilise par {process.name()} (PID {process.pid}).")
            if not assume_yes and not _confirm_stop(port, process):
                print("Arret annule.")
                continue

            print("Arret...")
            process.terminate()

            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                print("Arret normal impossible. Arret force...")
                process.kill()
                process.wait(timeout=5)

            print(f"Port {port} libere.")

        except psutil.NoSuchProcess:
            pass

        except psutil.AccessDenied:
            print(f"Permission refusee pour arreter le processus sur le port {port}.")
            sys.exit(1)

    if not found:
        print(f"Port {port} deja libre.")


def _confirm_stop(port: int, process: psutil.Process) -> bool:
    answer = input(f"Arreter {process.name()} (PID {process.pid}) sur le port {port} ? [y/N] ")
    return answer.strip().lower() in {"y", "yes", "o", "oui"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Libere prudemment un port local de developpement.")
    parser.add_argument("ports", nargs="+", type=int)
    parser.add_argument("--yes", action="store_true", help="Confirme automatiquement l'arret.")
    parser.add_argument(
        "--allowed-name",
        action="append",
        default=None,
        help="Nom de processus autorise a etre arrete. Option repetable.",
    )
    args = parser.parse_args()

    allowed_names = set(args.allowed_name or DEFAULT_ALLOWED_NAMES)
    for port in args.ports:
        free_port(port, allowed_names=allowed_names, assume_yes=args.yes)
        time.sleep(1)


if __name__ == "__main__":
    main()
