"""
Utility for parsing git diffs and validating review comments.
"""

import re
from typing import List, Dict, Optional


class DiffParser:
    def __init__(self, diff: str):
        self.diff = diff
        self.files = self._parse_diff()

    def _parse_diff(self) -> List[Dict]:
        files = []
        current_file = None
        current_hunk = None

        lines = self.diff.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            if line.startswith("diff --git"):
                if current_file:
                    files.append(current_file)
                current_file = {
                    "path": None,
                    "hunks": [],
                    "commentable_lines": {},
                }
                current_hunk = None

            elif line.startswith("+++ b/"):
                if current_file:
                    current_file["path"] = line[6:]

            elif line.startswith("@@"):
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if match:
                    new_start = int(match.group(3))
                    current_hunk = {
                        "new_start": new_start,
                        "current_line": new_start,
                        "lines": [],
                    }
                    if current_file:
                        current_file["hunks"].append(current_hunk)

            elif current_hunk is not None and current_file:
                if line.startswith("+") and not line.startswith("+++"):
                    line_number = current_hunk["current_line"]
                    line_content = line[1:]
                    current_file["commentable_lines"][line_number] = line_content
                    current_hunk["lines"].append(
                        {
                            "type": "added",
                            "line_number": line_number,
                            "content": line_content,
                        }
                    )
                    current_hunk["current_line"] += 1
                elif line.startswith("-") and not line.startswith("---"):
                    pass
                elif line.startswith(" "):
                    current_hunk["current_line"] += 1

            i += 1

        if current_file and current_file["path"]:
            files.append(current_file)

        return files

    def get_commentable_lines(self, file_path: str) -> Dict[int, str]:
        """Get all lines that can be commented on for a specific file."""
        for file in self.files:
            if file["path"] == file_path:
                return file["commentable_lines"]
        return {}

    def is_line_commentable(self, file_path: str, line_number: int) -> bool:
        """Check if a specific line can be commented on."""
        commentable = self.get_commentable_lines(file_path)
        return line_number in commentable

    def get_all_files(self) -> List[str]:
        """Get list of all files in the diff."""
        return [f["path"] for f in self.files if f["path"]]

    def get_added_lines_context(self) -> str:
        """Get a formatted string of all added lines with context for AI."""
        if not self.files:
            return "No changes detected in diff."

        context = []
        for file in self.files:
            if not file["path"] or not file["commentable_lines"]:
                continue

            context.append(f"\n File: {file['path']}")
            context.append("-" * 60)

            for line_num, content in sorted(file["commentable_lines"].items()):
                display_content = (
                    content[:100] + "..." if len(content) > 100 else content
                )
                context.append(f"  Line {line_num}: {display_content}")

        if not context:
            return "No added lines found in diff."

        return "\n".join(context)


def validate_and_filter_comments(
    comments: List[Dict], diff_parser: DiffParser
) -> List[Dict]:
    valid_comments = []
    invalid_count = 0

    for i, comment in enumerate(comments):
        if not isinstance(comment, dict):
            print(f"  Comment {i + 1}: Skipping non-dict comment")
            invalid_count += 1
            continue

        path = comment.get("path")
        line = comment.get("line")
        body = comment.get("body")

        if not all([path, line, body]):
            print(f"  Comment {i + 1}: Missing required fields (path/line/body)")
            invalid_count += 1
            continue

        if not isinstance(line, int):
            print(f"  Comment {i + 1}: Line number is not an integer: {line}")
            invalid_count += 1
            continue

        if not diff_parser.is_line_commentable(path, line):
            print(f"  Comment {i + 1}: Line {line} in '{path}' is NOT in the diff")

            available = diff_parser.get_commentable_lines(path)
            if available:
                available_lines = sorted(available.keys())
                print(f"      Available lines in {path}: {available_lines}")
            else:
                print(
                    f"      File '{path}' has no commentable lines or doesn't exist in diff"
                )

            invalid_count += 1
            continue

        valid_comments.append(
            {
                "path": path,
                "line": line,
                "side": comment.get("side", "RIGHT"),
                "body": body,
            }
        )
        print(f" Comment {i + 1}: Valid - {path}:{line}")

    print(f"\n Validation Summary:")
    print(f"   Total comments: {len(comments)}")
    print(f"   Valid: {len(valid_comments)}")
    print(f"   Invalid: {invalid_count}")

    return valid_comments
