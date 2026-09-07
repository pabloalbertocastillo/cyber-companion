"""Human-readable and JSON control client for the local companion."""
import argparse
import json
import sys
from .ipc import call
from .assistant import explain


def main():
    parser = argparse.ArgumentParser(prog="ccctl")
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "health", "insights", "stop"):
        sub.add_parser(name)
    for name in ("explain", "acknowledge"):
        sub.add_parser(name).add_argument("id")
    snooze = sub.add_parser("snooze")
    snooze.add_argument("id")
    snooze.add_argument("--seconds", type=int, default=1800)
    sub.add_parser("mute").add_argument("--seconds", type=int, default=3600)
    sub.add_parser("ask").add_argument("question")
    args = parser.parse_args()
    methods = {"status": "status.get", "health": "health.get", "insights": "insights.list",
               "explain": "insight.explain", "acknowledge": "insight.acknowledge", "snooze": "insight.snooze",
               "mute": "attention.mute", "ask": "assistant.ask", "stop": "daemon.stop"}
    params = {k: v for k, v in vars(args).items() if k in ("id", "seconds", "question")}
    try:
        result = call(methods[args.command], params, timeout=45 if args.command == "ask" else 4)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "status":
            print("WISP / 0.14\n" + explain(result))
            for name, health in result["health"].items():
                if health["state"] != "healthy":
                    print(f"  {name}: {health['message']}")
        elif type(result) is dict and "text" in result:
            print(result["text"])
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        print(f"Wisp: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
