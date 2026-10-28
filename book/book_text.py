"""Read the printable prose from ``book/text.md``.

The file is deliberately a small, hand-editable format rather than code:

    ## section
    key: value
    paragraph: |
        first line
        second line

Lines starting with ``#`` are notes and are skipped. Block lines are joined
with spaces, so the page layout does the wrapping; a line ending with a
backslash keeps a hard line break. Missing keys fail loudly with the file and
key name.
"""


def _join_block(lines):
    """Join block lines with spaces; a trailing backslash is a hard break."""
    out = []
    for line in lines:
        if not line:
            continue
        if line.endswith("\\"):
            out.append(line[:-1].rstrip() + "\n")
        else:
            out.append(line + " ")
    return "".join(out).strip()


class Text(dict):
    def __init__(self, path):
        self.path = path
        data = {}
        section = ""
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()

        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.rstrip()

            if line.startswith("## "):
                section = line[3:].strip()
                i += 1
                continue
            if (not line.strip() or line.lstrip().startswith("#")
                    or line.lstrip().startswith("<!--")):
                i += 1
                continue
            if raw.startswith("    ") or raw.startswith("\t"):
                raise SystemExit(
                    f"{path}:{i + 1}: indented line outside a '|' block")

            if ":" not in line:
                raise SystemExit(
                    f"{path}:{i + 1}: expected 'key: value'")
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            full = f"{section}.{key}" if section else key
            if full in data:
                raise SystemExit(
                    f"{path}:{i + 1}: duplicate key {full!r}")

            if value == "|":
                block = []
                i += 1
                while i < len(lines):
                    following = lines[i]
                    if following.startswith("    ") or following.startswith("\t"):
                        block.append(following.strip())
                        i += 1
                    elif not following.strip():
                        i += 1
                    else:
                        break
                data[full] = _join_block(block)
                continue

            data[full] = value
            i += 1

        super().__init__(data)

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise SystemExit(f"{self.path}: missing text key {key!r}")
