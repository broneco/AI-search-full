"""Export one committed release as a JHU-only, history-free source ZIP."""
import argparse
import json
from pathlib import Path

from scripts.publication.jhu import write_export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="Reviewed immutable release tag or commit")
    parser.add_argument("--output", required=True, type=Path, help="New ZIP path, normally under .local/publications")
    args = parser.parse_args(argv)
    manifest = write_export(Path(__file__).resolve().parent, args.ref, args.output)
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, ensure_ascii=False))
    print(f"Exported {len(manifest['files'])} files.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from None
