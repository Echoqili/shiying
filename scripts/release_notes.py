"""Print the CHANGELOG.md section for one version, used to build GitHub release notes."""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def section(version: str, text: str) -> str:
    pattern = re.compile(r'^## \[' + re.escape(version) + r'\][^\n]*\n(.*?)(?=^## \[|\Z)', re.M | re.S)
    match = pattern.search(text)
    if not match:
        raise SystemExit(f'CHANGELOG.md has no section for {version}')
    return match.group(1).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='Application version, for example 1.0.1')
    parser.add_argument('--output', type=Path, help='Write the section as UTF-8 instead of stdout')
    args = parser.parse_args()
    notes = section(args.version, (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8'))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(notes, encoding='utf-8')
    else:
        print(notes)


if __name__ == '__main__':
    main()
