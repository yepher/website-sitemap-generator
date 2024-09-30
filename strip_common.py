import os
import argparse
from collections import defaultdict

def read_markdown_files(directory):
    """Read all markdown files in a directory and return a dictionary with filename as key and content as list of lines."""
    markdown_files = {}
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                markdown_files[filename] = file.readlines()
    return markdown_files

def find_common_blocks(markdown_files, min_block_size=2):
    """
    Find common blocks of text across all markdown files.
    Args:
        markdown_files: Dictionary where key is filename, and value is list of file lines.
        min_block_size: Minimum block size to consider as common.
    Returns:
        common_blocks: Set of common line blocks found across all files.
    """
    line_blocks = defaultdict(int)

    for lines in markdown_files.values():
        seen_blocks = set()
        for i in range(len(lines)):
            for j in range(i + min_block_size, len(lines) + 1):
                block = tuple(lines[i:j])
                if block not in seen_blocks:
                    line_blocks[block] += 1
                    seen_blocks.add(block)

    # Consider blocks common if they appear in at least 80% of the files
    threshold = len(markdown_files) * 0.8
    common_blocks = {block for block, count in line_blocks.items() if count >= threshold}

    return common_blocks

def remove_common_blocks(markdown_files, common_blocks):
    """
    Remove common blocks from markdown files dynamically.
    Args:
        markdown_files: Dictionary of markdown file content.
        common_blocks: Set of common line blocks to remove.
    Returns:
        cleaned_files: Dictionary of cleaned markdown file content.
    """
    cleaned_files = {}

    for filename, lines in markdown_files.items():
        cleaned_lines = []
        i = 0
        length = len(lines)

        while i < length:
            block_found = False
            for block in common_blocks:
                block_size = len(block)
                if tuple(lines[i:i + block_size]) == block:
                    # Skip over the common block
                    i += block_size
                    block_found = True
                    break
            if not block_found:
                # If no block is found, just append the line
                cleaned_lines.append(lines[i])
                i += 1

        cleaned_files[filename] = cleaned_lines

    return cleaned_files

def write_cleaned_files(directory, cleaned_files):
    """Write cleaned markdown files back to the directory."""
    for filename, cleaned_lines in cleaned_files.items():
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w', encoding='utf-8') as file:
            file.writelines(cleaned_lines)

def process_markdown_directory(directory, min_block_size=2):
    # Step 1: Load all markdown files
    markdown_files = read_markdown_files(directory)

    # Step 2: Identify common blocks of text
    common_blocks = find_common_blocks(markdown_files, min_block_size=min_block_size)

    # Step 3: Remove common blocks from the files dynamically
    cleaned_files = remove_common_blocks(markdown_files, common_blocks)

    # Step 4: Save the cleaned files back to the directory
    write_cleaned_files(directory, cleaned_files)

    print(f"Processed {len(markdown_files)} markdown files. Common blocks removed.")

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Remove common redundant blocks from markdown files.")
    parser.add_argument('directory', type=str, help="Path to the directory containing markdown files.")
    parser.add_argument('--min-block-size', type=int, default=2, help="Minimum size of block of lines to consider as common (default: 2).")

    # Parse arguments
    args = parser.parse_args()

    # Process the markdown directory based on the provided arguments
    process_markdown_directory(args.directory, min_block_size=args.min_block_size)
