import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="youtube-dub v3 CLI")
    parser.add_argument(
        "command",
        choices=["create", "run", "status", "resume", "cancel", "validate", "clean"],
    )

    args = parser.parse_args()

    if args.command == "create":
        print("Create command (coming soon)")
    else:
        print(f"Command '{args.command}' not implemented yet.", file=sys.stderr)


if __name__ == "__main__":
    main()
