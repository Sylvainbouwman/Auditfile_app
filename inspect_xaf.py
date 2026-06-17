from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET


MAX_DEPTH = 5
SEARCH_WORDS = (
    "journal",
    "transaction",
    "entry",
    "line",
    "mutation",
    "document",
    "invoice",
)
LIKELY_MUTATION_PRIORITY = (
    "mutation",
    "transaction",
    "journal",
    "entry",
    "document",
    "invoice",
    "line",
)


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def find_first_auditfile(directory: Path) -> Path:
    candidates = sorted(
        [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".xaf", ".xml"}
        ],
        key=lambda path: path.name.casefold(),
    )
    if not candidates:
        raise FileNotFoundError("Geen .xaf of .xml bestand gevonden in deze map.")
    return candidates[0]


def analyze_xml(path: Path) -> dict:
    tag_counts: Counter[str] = Counter()
    tree: dict[str, set[str]] = defaultdict(set)
    search_hits: Counter[str] = Counter()
    search_paths: Counter[str] = Counter()
    candidate_scores: Counter[str] = Counter()
    candidate_child_counts: Counter[str] = Counter()
    stack: list[str] = []

    for event, elem in ET.iterparse(path, events=("start", "end")):
        name = local_name(elem.tag)

        if event == "start":
            stack.append(name)
            tag_counts[name] += 1

            if 1 < len(stack) <= MAX_DEPTH:
                tree["/".join(stack[:-1])].add(name)

            lower_name = name.casefold()
            if any(word in lower_name for word in SEARCH_WORDS):
                current_path = "/".join(stack)
                search_hits[name] += 1
                search_paths[current_path] += 1

                for index, word in enumerate(LIKELY_MUTATION_PRIORITY):
                    if word in lower_name:
                        candidate_scores[name] += (len(LIKELY_MUTATION_PRIORITY) - index) * 1_000
                        break

        else:
            if any(word in name.casefold() for word in SEARCH_WORDS):
                candidate_child_counts[name] = max(candidate_child_counts[name], len(elem))

            elem.clear()
            stack.pop()

    return {
        "tag_counts": tag_counts,
        "tree": tree,
        "search_hits": search_hits,
        "search_paths": search_paths,
        "candidate_scores": candidate_scores,
        "candidate_child_counts": candidate_child_counts,
    }


def render_tree(tree: dict[str, set[str]]) -> str:
    lines: list[str] = []
    roots = sorted({path.split("/", 1)[0] for path in tree}, key=str.casefold)

    def walk(path: str, depth: int) -> None:
        if depth >= MAX_DEPTH:
            return
        for child in sorted(tree.get(path, set()), key=str.casefold):
            lines.append(f"{'  ' * depth}- {child}")
            walk(f"{path}/{child}", depth + 1)

    for root in roots:
        lines.append(f"- {root}")
        walk(root, 1)

    return "\n".join(lines)


def choose_likely_mutation_tag(analysis: dict) -> str | None:
    candidate_scores: Counter[str] = analysis["candidate_scores"]
    candidate_child_counts: Counter[str] = analysis["candidate_child_counts"]
    tag_counts: Counter[str] = analysis["tag_counts"]

    candidates = [
        tag
        for tag in candidate_scores
        if candidate_child_counts[tag] > 0
    ]
    if not candidates:
        candidates = list(candidate_scores)
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda tag: (
            candidate_scores[tag],
            candidate_child_counts[tag],
            tag_counts[tag],
            tag.casefold(),
        ),
    )


def find_first_complete_element(path: Path, target_tag: str) -> str | None:
    capture_depth = 0
    captured = False

    for event, elem in ET.iterparse(path, events=("start", "end")):
        name = local_name(elem.tag)

        if event == "start":
            if not captured and capture_depth == 0 and name == target_tag:
                capture_depth = 1
            elif capture_depth > 0:
                capture_depth += 1
            continue

        if capture_depth > 0:
            capture_depth -= 1
            if capture_depth == 0 and name == target_tag:
                captured = True
                return ET.tostring(elem, encoding="unicode")
            continue

        elem.clear()

    return None


def main() -> None:
    directory = Path(__file__).resolve().parent
    auditfile = find_first_auditfile(directory)

    print(f"Bestand: {auditfile.name}")
    print(f"Grootte: {auditfile.stat().st_size:,} bytes")

    analysis = analyze_xml(auditfile)

    print("\n1. Unieke XML-tags met aantallen")
    for tag, count in sorted(analysis["tag_counts"].items(), key=lambda item: item[0].casefold()):
        print(f"{tag}: {count}")

    print(f"\n2. XML-boomstructuur tot {MAX_DEPTH} niveaus diep")
    print(render_tree(analysis["tree"]) or "Geen boomstructuur gevonden.")

    print("\n3. Gevonden tags met journal, transaction, entry, line, mutation, document of invoice")
    if analysis["search_hits"]:
        for tag, count in analysis["search_hits"].most_common():
            print(f"{tag}: {count}")
    else:
        print("Geen bijpassende tags gevonden.")

    print("\nMeest voorkomende paden voor gevonden tags")
    if analysis["search_paths"]:
        for path, count in analysis["search_paths"].most_common(30):
            print(f"{path}: {count}")
    else:
        print("Geen bijpassende paden gevonden.")

    likely_tag = choose_likely_mutation_tag(analysis)
    print("\n4. Volledig voorbeeld van de meest waarschijnlijke mutatie-tag")
    if not likely_tag:
        print("Geen waarschijnlijke mutatie-tag gevonden.")
        return

    print(f"Gekozen tag: {likely_tag}")
    sample = find_first_complete_element(auditfile, likely_tag)
    if sample:
        print(sample)
    else:
        print("Geen volledig voorbeeld gevonden.")


if __name__ == "__main__":
    main()
