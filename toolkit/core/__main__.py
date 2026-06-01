from __future__ import annotations

import argparse
import json

from .facade import ToolkitCore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="game root or launcher path")
    parser.add_argument("--maps", action="store_true")
    parser.add_argument("--entries", action="store_true")
    parser.add_argument("--records", action="store_true")
    args = parser.parse_args()

    core = ToolkitCore()
    summary = core.load_project(args.path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.maps:
        print(json.dumps(core.maps(), ensure_ascii=False, indent=2))
    if args.entries:
        print(json.dumps(core.translation_entries(), ensure_ascii=False, indent=2))
    if args.records:
        print(json.dumps(core.data_records(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

