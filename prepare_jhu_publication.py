"""Plan or apply source files to the independent Forgejo clone; never commits/pushes."""
import argparse
import json
from pathlib import Path

from scripts.publication.sync import sync


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expect-head")
    args = parser.parse_args(argv)
    print(json.dumps(sync(args.archive, args.destination, apply=args.apply, expect_head=args.expect_head),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from None
