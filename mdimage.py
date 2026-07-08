from pathlib import Path
import argparse
import os
import re
import shutil
from typing import List, Optional, Set

ROOT = Path(__file__).resolve().parent

wiki_link_pattern = re.compile(r"(!\[\[)([^\]\n]+?\.png)(\]\])")
markdown_link_pattern = re.compile(r"(!\[[^\]]*\]\()([^\)\n]+?\.png)(\))")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy PNG images referenced from markdown files into a destination folder."
    )
    parser.add_argument(
        "markdown_path",
        nargs="?",
        default=".",
        help="Path to a markdown file or directory containing markdown files (default: current folder)",
    )
    parser.add_argument(
        "-i",
        "--images-dir",
        default="Main Images",
        help="Directory containing the PNG files to copy (default: Main Images)",
    )
    parser.add_argument(
        "-d",
        "--destination-dir",
        default="TEST",
        help="Directory where matching PNG files will be copied (default: TEST)",
    )
    parser.add_argument(
        "-m",
        "--markdown-output-dir",
        default=None,
        help="Directory where rewritten markdown copies will be saved (default: next to the original markdown file)",
    )
    return parser.parse_args()


def resolve_path(path_value: str, base_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def get_markdown_files(markdown_path: Path) -> List[Path]:
    if markdown_path.is_file():
        return [markdown_path] if markdown_path.suffix.lower() == ".md" else []
    if not markdown_path.exists():
        return []
    return sorted([path for path in markdown_path.rglob("*.md") if path.is_file()])


def extract_image_references(markdown_text: str) -> Set[str]:
    refs = set()
    for match in wiki_link_pattern.finditer(markdown_text):
        refs.add(match.group(2).strip())
    for match in markdown_link_pattern.finditer(markdown_text):
        target = match.group(2).strip()
        if target.lower().endswith(".png"):
            refs.add(target)
    return refs


def resolve_image_path(reference: str, markdown_file: Path, images_dir: Path, base_dir: Path) -> Optional[Path]:
    candidate_text = reference.strip().strip("'\"")
    if not candidate_text:
        return None

    candidate_path = Path(candidate_text)

    if candidate_path.is_absolute():
        if candidate_path.exists() and candidate_path.is_file() and candidate_path.suffix.lower() == ".png":
            return candidate_path
        return None

    search_locations = [
        markdown_file.parent / candidate_path,
        base_dir / candidate_path,
        images_dir / candidate_path.name,
    ]

    for location in search_locations:
        if location.exists() and location.is_file() and location.suffix.lower() == ".png":
            return location

    if candidate_path.suffix.lower() == ".png":
        for match in images_dir.rglob("*.png"):
            if match.name == candidate_path.name:
                return match

    return None


def get_destination_suffix(destination_dir: Path, base_dir: Path) -> str:
    try:
        rel_destination = destination_dir.relative_to(base_dir)
        folder_suffix = str(rel_destination).replace("\\", "_").replace("/", "_")
    except Exception:
        folder_suffix = destination_dir.name

    return re.sub(r"[^A-Za-z0-9._-]+", "_", folder_suffix).strip("._")


def build_markdown_copy_path(markdown_file: Path, output_dir: Optional[Path] = None) -> Path:
    if output_dir is None:
        return markdown_file.with_name(f"{markdown_file.stem}_copy{markdown_file.suffix}")
    return output_dir / f"{markdown_file.stem}_copy{markdown_file.suffix}"


def display_path(path: Path, base_dir: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def build_image_copy_name(image_path: Path, destination_dir: Path, base_dir: Path) -> str:
    return image_path.name


def build_static_image_link(image_name: str, destination_dir: Path, base_dir: Path) -> str:
    try:
        rel_destination = destination_dir.relative_to(base_dir)
        target_path = str(rel_destination).replace("\\", "/")
    except Exception:
        target_path = destination_dir.name

    if target_path:
        return f"{target_path}/{image_name}"
    return image_name


def rewrite_markdown_copy(markdown_text: str, markdown_file: Path, images_dir: Path, destination_dir: Path, base_dir: Path) -> str:
    def replace_wiki(match: re.Match) -> str:
        _, target, _ = match.groups()
        resolved = resolve_image_path(target, markdown_file, images_dir, base_dir)
        if resolved is None:
            return match.group(0)
        if resolved.parent != images_dir and resolved.parent != markdown_file.parent:
            return match.group(0)
        image_link = build_static_image_link(resolved.name, destination_dir, base_dir)
        return f"![Description of image]({image_link})"

    def replace_markdown(match: re.Match) -> str:
        _, target, _ = match.groups()
        resolved = resolve_image_path(target, markdown_file, images_dir, base_dir)
        if resolved is None:
            return match.group(0)
        if resolved.parent != images_dir and resolved.parent != markdown_file.parent:
            return match.group(0)
        image_link = build_static_image_link(resolved.name, destination_dir, base_dir)
        return f"![Description of image]({image_link})"

    rewritten = wiki_link_pattern.sub(replace_wiki, markdown_text)
    return markdown_link_pattern.sub(replace_markdown, rewritten)


def main() -> None:
    args = parse_args()
    base_dir = ROOT

    markdown_path = resolve_path(args.markdown_path, base_dir)
    images_dir = resolve_path(args.images_dir, base_dir)
    destination_dir = resolve_path(args.destination_dir, base_dir)
    markdown_output_dir = resolve_path(args.markdown_output_dir, base_dir) if args.markdown_output_dir else None

    destination_dir.mkdir(parents=True, exist_ok=True)

    markdown_files = get_markdown_files(markdown_path)
    if not markdown_files:
        print(f"No markdown files found at: {markdown_path}")
        return

    copied = []
    skipped = []
    markdown_copies = []

    for markdown_file in markdown_files:
        if markdown_file.parent == destination_dir:
            continue

        suffix = get_destination_suffix(destination_dir, base_dir)
        if suffix and markdown_file.name.startswith(f"{suffix}__"):
            continue

        try:
            text = markdown_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        copied_for_file = False
        for reference in extract_image_references(text):
            image_path = resolve_image_path(reference, markdown_file, images_dir, base_dir)
            if image_path is None:
                continue

            if image_path.parent != images_dir and image_path.parent != markdown_file.parent:
                continue

            copied_for_file = True
            dest = destination_dir / image_path.name
            if dest.exists():
                skipped.append((display_path(markdown_file, base_dir), image_path.name, "already_exists"))
                continue

            # Preserve any existing files in the destination directory; only add new copies.
            shutil.copy2(image_path, dest)
            copied.append((display_path(markdown_file, base_dir), image_path.name))

        if copied_for_file:
            markdown_copy_path = build_markdown_copy_path(markdown_file, markdown_output_dir)
            if not markdown_copy_path.exists():
                rewritten_text = rewrite_markdown_copy(text, markdown_file, images_dir, destination_dir, base_dir)
                markdown_copy_path.parent.mkdir(parents=True, exist_ok=True)
                markdown_copy_path.write_text(rewritten_text, encoding="utf-8")
                markdown_copies.append((display_path(markdown_file, base_dir), markdown_copy_path.name))

    print(f"Using markdown path: {markdown_path}")
    print(f"Using images directory: {images_dir}")
    print(f"Copy destination: {destination_dir}")
    print(f"Copied {len(copied)} file(s)")

    for source_md, image_name in copied[:20]:
        print(f"- {source_md} -> {image_name}")

    if len(copied) > 20:
        print(f"... and {len(copied) - 20} more")

    if markdown_copies:
        print(f"Created {len(markdown_copies)} markdown copy file(s)")
        for source_md, copied_md_name in markdown_copies[:20]:
            print(f"- {source_md} -> {copied_md_name}")

    if skipped:
        print(f"Skipped {len(skipped)} existing or unresolved file(s)")


if __name__ == "__main__":
    main()
