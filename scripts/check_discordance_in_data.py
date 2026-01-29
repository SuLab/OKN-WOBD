#!/usr/bin/env python3
"""Check if local GXA TTL files contain any discordant genes (same gene, both up and down)."""
import re
from pathlib import Path

def main():
    data_dir = Path(__file__).parent.parent / "data" / "gene_expression"
    if not data_dir.exists():
        print(f"Data dir not found: {data_dir}")
        return

    gene_to_signs: dict[str, set[str]] = {}
    fc_re = re.compile(r'spokegenelab:log2fc\s+"([^"]+)"')
    obj_re = re.compile(r'biolink:object\s+(\S+)')

    for ttl in sorted(data_dir.glob("*.ttl")):
        lines = ttl.read_text().split("\n")
        for i, line in enumerate(lines):
            fc_match = fc_re.search(line)
            if fc_match:
                try:
                    fc = float(fc_match.group(1))
                except ValueError:
                    continue
                sign = "up" if fc > 0 else "down" if fc < 0 else "zero"
                # object is typically on next line
                for j in range(i + 1, min(i + 4, len(lines))):
                    obj_match = obj_re.search(lines[j])
                    if obj_match:
                        gene = obj_match.group(1).rstrip(" .")
                        gene_to_signs.setdefault(gene, set()).add(sign)
                        break

    discordant = [g for g, signs in gene_to_signs.items() if "up" in signs and "down" in signs]
    print(f"Total genes with DE: {len(gene_to_signs)}")
    print(f"Discordant genes (up in some, down in others): {len(discordant)}")
    if discordant:
        print("Examples:", discordant[:10])
    else:
        print("No discordant genes found in local TTL files.")
        print("(FRINK endpoint may have different/richer data.)")

if __name__ == "__main__":
    main()
