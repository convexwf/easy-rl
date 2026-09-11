#!/usr/bin/env python3
"""Build the single-file EasyRL documentation.

The chapter files remain the source of truth.  This script only describes the
reading order and performs the small transformations needed when files that
originally lived in different directories are rendered as one document.

Usage (from the repository root)::

    python3 easy-rl/scripts/build_combined_docs.py
    python3 easy-rl/scripts/build_combined_docs.py --check

The ``--check`` mode rebuilds the document in memory and exits non-zero when
the checked-in output is stale.  This makes it suitable for a CI job.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, unquote, urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parent
DOCS_ROOT = REPOSITORY_ROOT / "docs"
DEFAULT_OUTPUT = DOCS_ROOT / "easy-rl-complete.md"
RAW_GITHUB_DOCS_URL = (
    # Keep generated documents portable outside the repository checkout.
    "https://raw.githubusercontent.com/convexwf/easy-rl/refs/heads/master/docs"
)


@dataclass(frozen=True)
class DocumentPart:
    """One source document in the generated reading order."""

    path: str | None
    title: str
    kind: str = "chapter"
    empty_note: str | None = None


@dataclass(frozen=True)
class Section:
    title: str
    parts: tuple[DocumentPart, ...]


# Keep this list as the public table of contents for the single-file edition.
# When upstream adds or renames a chapter, update this list and rerun the
# script.  Source files themselves should not be copied into this file by hand.
SECTIONS: tuple[Section, ...] = (
    Section(
        "第一部分：强化学习基础",
        (
            DocumentPart("chapter1/chapter1.md", "第 1 章 强化学习基础"),
            DocumentPart(
                "chapter1/chapter1_questions&keywords.md",
                "第 1 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter2/chapter2.md", "第 2 章 马尔可夫决策过程（MDP）"),
            DocumentPart(
                "chapter2/chapter2_questions&keywords.md",
                "第 2 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter3/chapter3.md", "第 3 章 表格型方法"),
            DocumentPart(
                "chapter3/chapter3_questions&keywords.md",
                "第 3 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart(
                "chapter3/project1.md",
                "项目一：使用 Q-learning 解决悬崖寻路问题",
                kind="project",
            ),
        ),
    ),
    Section(
        "第二部分：策略优化与深度价值方法",
        (
            DocumentPart("chapter4/chapter4.md", "第 4 章 策略梯度"),
            DocumentPart(
                "chapter4/chapter4_questions&keywords.md",
                "第 4 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter5/chapter5.md", "第 5 章 近端策略优化（PPO）算法"),
            DocumentPart(
                "chapter5/chapter5_questions&keywords.md",
                "第 5 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter6/chapter6.md", "第 6 章 深度 Q 网络（DQN）基础"),
            DocumentPart(
                "chapter6/chapter6_questions&keywords.md",
                "第 6 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter7/chapter7.md", "第 7 章 深度 Q 网络（DQN）进阶技巧"),
            DocumentPart(
                "chapter7/chapter7_questions&keywords.md",
                "第 7 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart(
                "chapter7/project2.md",
                "项目二：使用 DQN 实现 CartPole-v0",
                kind="project",
            ),
            DocumentPart("chapter8/chapter8.md", "第 8 章 针对连续动作的深度 Q 网络"),
            DocumentPart(
                "chapter8/chapter8_questions&keywords.md",
                "第 8 章习题与关键词",
                kind="exercise",
            ),
        ),
    ),
    Section(
        "第三部分：Actor-Critic 与算法扩展",
        (
            DocumentPart("chapter9/chapter9.md", "第 9 章 演员-评论员算法"),
            DocumentPart(
                "chapter9/chapter9_questions&keywords.md",
                "第 9 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter10/chapter10.md", "第 10 章 稀疏奖励"),
            DocumentPart(
                "chapter10/chapter10_questions&keywords.md",
                "第 10 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart("chapter11/chapter11.md", "第 11 章 模仿学习"),
            DocumentPart(
                "chapter11/chapter11_questions&keywords.md",
                "第 11 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart(
                "chapter12/chapter12.md",
                "第 12 章 深度确定性策略梯度（DDPG）算法",
            ),
            DocumentPart(
                "chapter12/chapter12_questions&keywords.md",
                "第 12 章习题与关键词",
                kind="exercise",
            ),
            DocumentPart(
                "chapter12/project3.md",
                "项目三：使用 Policy-Based 方法实现 Pendulum-v0",
                kind="project",
            ),
        ),
    ),
    Section(
        "第四部分：前沿专题",
        (
            DocumentPart("chapter13/chapter13.md", "第 13 章 AlphaStar 论文解读"),
            DocumentPart(
                "chapter14/ls-imagine.md",
                "第 14 章 ICLR 2025 Oral：LS-Imagine 在开放世界中进行强化学习",
            ),
            DocumentPart(
                "chapter15/chapter15.md",
                "第 15 章 视觉强化学习论文清单",
                empty_note=(
                    "本章源文件目前为空。相关论文清单请参考 "
                    "[Awesome Visual RL](https://github.com/qiwang067/awesome-visual-rl)。"
                ),
            ),
            DocumentPart("chapter16/chapter16.md", "第 16 章 世界模型的本质"),
        ),
    ),
    Section(
        "附录",
        (
            DocumentPart("errata.md", "附录 A：纸质版勘误修订表", kind="appendix"),
        ),
    ),
)


FRONT_MATTER_TEMPLATE = """---
title: EasyRL：强化学习完整教程
authors:
  - 王琦
  - 杨毅远
  - 江季
language: zh-CN
tags:
  - reinforcement-learning
  - tutorial
published_at: {published_at}
updated_at: {updated_at}
---

# EasyRL：强化学习完整教程

## 文档信息

| 项目 | 内容 |
| --- | --- |
| **文档标题** | EasyRL：强化学习完整教程 |
| **文档版本** | 由章节源文件自动生成 |
| **文档类型** | 教程合集 |
| **源文件** | `easy-rl/docs/chapter*/`、`easy-rl/docs/errata.md` |
| **生成脚本** | `easy-rl/scripts/build_combined_docs.py` |

> 本文件是生成产物。请修改章节源文件和生成脚本中的目录清单，然后重新运行脚本，不要直接编辑本文件。

## 阅读说明

本文档按从基础到进阶的顺序合并 EasyRL 的章节、习题和实战项目。章节正文仍以 `docs/chapter*/` 下的文件为维护源；本文件适合连续阅读、搜索和导出为 PDF。

## 目录

"""


def git_commit_dates() -> tuple[str, str]:
    """Return (first source commit date, latest repository commit date).

    Git's committer date is used because it records when the commit actually
    entered the repository.  Dates are rendered as ISO calendar dates so the
    frontmatter stays compatible with the existing metadata convention.
    """

    def run_git(*args: str) -> list[str]:
        command = ["git", "-C", str(REPOSITORY_ROOT), *args]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(
                "cannot read Git commit dates; run the builder inside a Git checkout"
            ) from exc
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    latest = run_git("log", "-1", "--format=%cI")
    if not latest:
        raise RuntimeError("Git repository has no commits; cannot set document dates")

    source_paths = [part.path for part in iter_parts() if part.path is not None]
    first_source = run_git(
        "log",
        "--reverse",
        "--format=%cI",
        "--",
        *[f"docs/{path}" for path in source_paths],
    )
    published_at = (first_source[0] if first_source else latest[0])[:10]
    updated_at = latest[0][:10]
    return published_at, updated_at


def slugify(title: str) -> str:
    """Return a GitHub-style anchor for headings used in our TOC."""

    # GitHub keeps CJK characters in anchors.  Removing punctuation and using
    # hyphens for whitespace is sufficiently stable for this generated file.
    value = title.strip().lower()
    value = re.sub(r"[`*_~]", "", value)
    value = re.sub(r"[^\w\u3400-\u9fff\- ]+", "", value)
    value = re.sub(r"\s+", "-", value)
    return value.strip("-")


def iter_parts() -> Iterable[DocumentPart]:
    for section in SECTIONS:
        yield from section.parts


def source_path(part: DocumentPart) -> Path | None:
    return DOCS_ROOT / part.path if part.path else None


def validate_manifest() -> None:
    seen: set[str] = set()
    for part in iter_parts():
        if part.path is None:
            continue
        if part.path in seen:
            raise ValueError(f"source appears more than once: {part.path}")
        seen.add(part.path)
        path = source_path(part)
        assert path is not None
        if not path.is_file():
            raise FileNotFoundError(f"manifest source does not exist: {path}")

    # Do not silently omit a new chapter file added by upstream.  The next
    # build should tell the maintainer to add it to the ordered manifest.
    listed_chapters = {path for path in seen if path.startswith("chapter")}
    discovered_chapters = {
        path.relative_to(DOCS_ROOT).as_posix()
        for path in DOCS_ROOT.glob("chapter*/*.md")
    }
    missing_from_manifest = discovered_chapters - listed_chapters
    if missing_from_manifest:
        names = ", ".join(sorted(missing_from_manifest))
        raise ValueError(f"chapter source is not in the manifest: {names}")


def split_target(target: str) -> tuple[str, str]:
    """Separate a local path from its query/fragment suffix."""

    match = re.match(r"([^?#]*)(.*)$", target)
    assert match is not None
    return match.group(1), match.group(2)


def rewrite_image_target(target: str, source: Path) -> str:
    """Turn a local image path into a stable raw GitHub URL."""

    if target.startswith(("http://", "https://", "mailto:", "data:", "#", "/")):
        return target
    path_text, suffix = split_target(target)
    if not path_text:
        return target
    resolved = (source.parent / Path(path_text)).resolve()
    try:
        relative = resolved.relative_to(DOCS_ROOT.resolve())
    except ValueError:
        return target
    encoded_path = quote(relative.as_posix(), safe="/-._~!$&'()*+,;=:@")
    return f"{RAW_GITHUB_DOCS_URL}/{encoded_path}{suffix}"


MARKDOWN_TARGET = re.compile(
    r"(?P<prefix>!\[[^\]]*\]\()(?P<target><[^>]+>|[^)\s]+)(?P<rest>[^)]*\))"
)
HTML_IMAGE_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
HTML_ATTRIBUTE = re.compile(
    r"\b(?P<name>[a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*"
    r"(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))",
    re.IGNORECASE,
)
ALIGN_DIV_TAG = re.compile(r"</?div\s+align\s*=\s*[\"']?center[\"']?\s*/?>", re.IGNORECASE)
BARE_DIV_CLOSE_TAG = re.compile(r"</div\s*>", re.IGNORECASE)
FIGURE_TAG = re.compile(r"</?figure(?:\s+[^>]*)?>", re.IGNORECASE)
FIGCAPTION_TAG = re.compile(r"</?figcaption(?:\s+[^>]*)?>", re.IGNORECASE)


def html_attribute(tag: str, name: str) -> str | None:
    """Read one HTML attribute from an image tag."""

    for match in HTML_ATTRIBUTE.finditer(tag):
        if match.group("name").lower() == name.lower():
            return next(
                value
                for value in (
                    match.group("double"),
                    match.group("single"),
                    match.group("bare"),
                )
                if value is not None
            )
    return None


def image_alt_text(raw_target: str) -> str:
    """Choose useful alt text when an HTML image has no ``alt`` attribute."""

    path_text, _ = split_target(raw_target)
    if path_text.startswith(("http://", "https://")):
        path_text = urlsplit(path_text).path
    name = Path(unquote(path_text)).name
    stem = Path(name).stem
    return stem or "image"


def html_image_to_markdown(tag: str, source: Path) -> str:
    """Convert one HTML image tag to standard Markdown image syntax."""

    raw_target = html_attribute(tag, "src")
    if raw_target is None:
        return tag
    target = rewrite_image_target(raw_target, source)
    alt = html_attribute(tag, "alt") or image_alt_text(raw_target)
    return f"![{alt}]({target})"


def rewrite_assets(line: str, source: Path, align_div_closes: int = 0) -> str:
    converted_html_image = bool(HTML_IMAGE_TAG.search(line))

    def markdown_replacer(match: re.Match[str]) -> str:
        target = match.group("target")
        if target.startswith("<") and target.endswith(">"):
            inner = target[1:-1]
            target = f"<{rewrite_image_target(inner, source)}>"
        else:
            target = rewrite_image_target(target, source)
        return f"{match.group('prefix')}{target}{match.group('rest')}"

    line = MARKDOWN_TARGET.sub(markdown_replacer, line)
    line = HTML_IMAGE_TAG.sub(
        lambda match: html_image_to_markdown(match.group(0), source),
        line,
    )
    # The original chapters use HTML containers to center images and captions.
    # Once images are Markdown, those containers would prevent some Markdown
    # renderers from parsing them, so remove the alignment wrappers and keep
    # the caption text.
    line = ALIGN_DIV_TAG.sub("", line)
    line = FIGURE_TAG.sub("", line)
    if align_div_closes:
        line = BARE_DIV_CLOSE_TAG.sub("", line, count=align_div_closes)
    line = FIGCAPTION_TAG.sub("", line)
    return line.strip() if converted_html_image else line


def transform_source(part: DocumentPart) -> str:
    path = source_path(part)
    if path is None:
        return f"### {part.title}\n\n{part.empty_note or ''}\n"

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    result: list[str] = []
    in_fence = False
    align_div_depth = 0
    title_written = False
    for line in lines:
        if re.match(r"^\s*```", line):
            in_fence = not in_fence
            result.append(line)
            continue

        heading = re.match(r"^(#{1,6})(\s+)(.*?)(\s*)$", line)
        if heading and not in_fence:
            level = len(heading.group(1))
            if not title_written and level == 1:
                result.append(f"### {part.title}")
                title_written = True
            else:
                result.append(f"{'#' * min(level + 2, 6)} {heading.group(3).strip()}")
            continue

        if in_fence:
            result.append(line)
            continue

        align_opens = len(ALIGN_DIV_TAG.findall(line))
        align_closes = len(BARE_DIV_CLOSE_TAG.findall(line))
        closings_to_remove = min(align_div_depth + align_opens, align_closes)
        align_div_depth += align_opens - closings_to_remove
        result.append(rewrite_assets(line, path, closings_to_remove))

    if not title_written:
        result.insert(0, f"### {part.title}")
        if not lines and part.empty_note:
            result.append(part.empty_note)
    return "\n".join(result).strip() + "\n"


def build_document() -> str:
    validate_manifest()
    published_at, updated_at = git_commit_dates()
    front_matter = FRONT_MATTER_TEMPLATE.format(
        published_at=published_at,
        updated_at=updated_at,
    )
    pieces = [front_matter.rstrip(), ""]
    for section in SECTIONS:
        pieces.append(f"- [{section.title}](#{slugify(section.title)})")
        for part in section.parts:
            pieces.append(f"  - [{part.title}](#{slugify(part.title)})")
    pieces.extend(["", "---", ""])

    for section in SECTIONS:
        pieces.extend([f"## {section.title}", ""])
        for part in section.parts:
            pieces.append(transform_source(part).rstrip())
            pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"output path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="check whether the existing output matches the generated content",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    generated = build_document()

    if args.check:
        if not output.is_file():
            print(f"stale: missing output {output}", file=sys.stderr)
            return 1
        current = output.read_text(encoding="utf-8")
        if current != generated:
            print(f"stale: regenerate {output}", file=sys.stderr)
            return 1
        print(f"up to date: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"generated {output} ({len(generated.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
