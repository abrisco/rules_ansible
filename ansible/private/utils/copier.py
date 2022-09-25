#!/usr/bin/env python3

import shutil
import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--destination",
        required=True,
        type=Path,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    args.destination.parent.mkdir(exist_ok=True, parents=True)

    shutil.copyfile(str(args.source), str(args.destination), follow_symlinks=True)


if __name__ == "__main__":
    main()
