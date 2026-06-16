#!/usr/bin/env python3
"""
Submission Package Creator for LLM_robot_2.

Creates a ZIP file with all required submission materials, excluding
unnecessary files like logs, caches, and temporary files.

Story: 2.5 - Monitoring, Logging, and Evaluation
AC #8: Create submission package in NAME_STUDENTID.zip format

Usage:
    python scripts/create_submission.py --name "Your Name" --id "20251234"
    python scripts/create_submission.py  # Interactive mode
"""

import os
import zipfile
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Set


class SubmissionPackager:
    """
    Creates submission ZIP package for LLM_robot_2 project.

    Includes:
    - Source code (src/, tests/)
    - Webots world files (worlds/)
    - Documentation (README.md, docs/)
    - Configuration (requirements.txt, .env.example)
    - Evaluation materials (docs/evaluation/)

    Excludes:
    - Logs (logs/)
    - Cache (__pycache__/, *.pyc)
    - Virtual environments (venv/, .venv/)
    - IDE files (.vscode/, .idea/)
    - Git files (.git/)
    - Temporary files (*.tmp, *.log)
    """

    # Files and directories to include
    INCLUDE_PATTERNS = [
        "src/**/*.py",
        "tests/**/*.py",
        "tests/**/*.json",
        "worlds/**/*.wbt",
        "worlds/**/*.proto",
        "docs/**/*.md",
        "scripts/**/*.py",
        "README.md",
        "requirements.txt",
        ".env.example",
        "pytest.ini",
        ".gitignore"
    ]

    # Directories to exclude (top-level)
    EXCLUDE_DIRS = {
        "logs",
        "__pycache__",
        ".pytest_cache",
        "venv",
        ".venv",
        "BMAD-METHOD",
        ".git",
        ".vscode",
        ".idea",
        "node_modules",
        ".DS_Store"
    }

    # File extensions to exclude
    EXCLUDE_EXTENSIONS = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".log",
        ".tmp",
        ".cache",
        ".coverage"
    }

    def __init__(self, project_root: str = "."):
        """
        Initialize submission packager.

        Args:
            project_root: Path to project root directory
        """
        self.project_root = Path(project_root).resolve()
        self.files_to_include: List[Path] = []
        self.total_size = 0

    def should_exclude(self, file_path: Path) -> bool:
        """
        Check if file should be excluded from submission.

        Args:
            file_path: Path to check

        Returns:
            True if file should be excluded
        """
        # Check if any parent directory is in exclude list
        for part in file_path.parts:
            if part in self.EXCLUDE_DIRS:
                return True

        # Check file extension
        if file_path.suffix in self.EXCLUDE_EXTENSIONS:
            return True

        # Exclude hidden files (except .env.example, .gitignore)
        if file_path.name.startswith('.') and file_path.name not in ['.env.example', '.gitignore']:
            return True

        return False

    def collect_files(self) -> int:
        """
        Collect all files to include in submission.

        Returns:
            Number of files collected
        """
        print("Collecting files for submission...")

        # Collect all Python files and other source files
        for pattern in self.INCLUDE_PATTERNS:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file() and not self.should_exclude(file_path):
                    self.files_to_include.append(file_path)
                    self.total_size += file_path.stat().st_size

        # Remove duplicates and sort
        self.files_to_include = sorted(set(self.files_to_include))

        print(f"✓ Collected {len(self.files_to_include)} files")
        print(f"✓ Total size: {self.total_size / (1024*1024):.2f} MB")

        return len(self.files_to_include)

    def create_zip(self, output_name: str, student_name: str, student_id: str) -> Path:
        """
        Create submission ZIP file.

        Args:
            output_name: Output ZIP filename (without .zip extension)
            student_name: Student name for metadata
            student_id: Student ID for metadata

        Returns:
            Path to created ZIP file
        """
        zip_filename = f"{output_name}.zip"
        zip_path = self.project_root / zip_filename

        # Remove existing ZIP if present
        if zip_path.exists():
            print(f"Removing existing file: {zip_filename}")
            zip_path.unlink()

        print(f"Creating submission package: {zip_filename}")

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add metadata file
            metadata = self._create_metadata(student_name, student_id)
            zipf.writestr("SUBMISSION_INFO.txt", metadata)

            # Add all collected files
            for file_path in self.files_to_include:
                # Get relative path from project root
                arc_name = file_path.relative_to(self.project_root)
                zipf.write(file_path, arc_name)
                print(f"  + {arc_name}")

        final_size = zip_path.stat().st_size
        print(f"\n✓ Submission package created successfully!")
        print(f"✓ File: {zip_path}")
        print(f"✓ Size: {final_size / (1024*1024):.2f} MB")

        # Check size limit (100MB warning)
        if final_size > 100 * 1024 * 1024:
            print(f"\n⚠️  WARNING: Package size exceeds 100MB!")
            print(f"   Consider removing unnecessary files.")
        else:
            print(f"✓ Size check passed (< 100MB)")

        return zip_path

    def _create_metadata(self, student_name: str, student_id: str) -> str:
        """Create submission metadata text."""
        lines = [
            "="*60,
            "LLM_ROBOT_2 - Submission Package",
            "="*60,
            "",
            f"Student Name: {student_name}",
            f"Student ID: {student_id}",
            f"Project: Multi-Agent LLM Robot Control System",
            f"Submission Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Package Contents:",
            "- Source code (src/)",
            "- Test files (tests/)",
            "- Webots world files (worlds/)",
            "- Documentation (README.md, docs/)",
            "- Evaluation materials (docs/evaluation/)",
            "- Requirements (requirements.txt)",
            "",
            "Setup Instructions:",
            "1. Extract ZIP file",
            "2. Install dependencies: pip install -r requirements.txt",
            "3. Set up .env file with OPENAI_API_KEY",
            "4. Open Webots and load worlds/rescue_arena.wbt",
            "5. Run: python src/main.py",
            "",
            "Evaluation:",
            "- Run evaluation tests: pytest tests/evaluation/",
            "- Generate benchmark report: python -c 'from src.utils import BenchmarkReport; BenchmarkReport.generate_from_logs()'",
            "- View evaluation spec: docs/evaluation/evaluation_spec.md",
            "",
            "="*60,
        ]
        return '\n'.join(lines)

    def verify_package(self, zip_path: Path) -> bool:
        """
        Verify submission package contents.

        Args:
            zip_path: Path to ZIP file

        Returns:
            True if package is valid
        """
        print(f"\nVerifying package: {zip_path.name}")

        required_files = [
            "README.md",
            "requirements.txt",
            "src/main.py",
            "src/orchestrator.py",
            "docs/evaluation/evaluation_spec.md",
            "docs/evaluation/presentation_script.md"
        ]

        with zipfile.ZipFile(zip_path, 'r') as zipf:
            file_list = zipf.namelist()

            # Check required files
            missing_files = []
            for required in required_files:
                if required not in file_list:
                    missing_files.append(required)

            if missing_files:
                print("✗ Missing required files:")
                for missing in missing_files:
                    print(f"  - {missing}")
                return False

            print("✓ All required files present")
            print(f"✓ Total files in package: {len(file_list)}")

        return True


def main():
    """Main entry point for submission packaging."""
    parser = argparse.ArgumentParser(
        description="Create submission package for LLM_robot_2"
    )
    parser.add_argument(
        "--name",
        help="Student name (e.g., 'Hong Gildong')",
        default=None
    )
    parser.add_argument(
        "--id",
        help="Student ID (e.g., '20251234')",
        default=None
    )
    parser.add_argument(
        "--project-root",
        help="Path to project root directory",
        default="."
    )

    args = parser.parse_args()

    # Interactive mode if name/id not provided
    student_name = args.name
    student_id = args.id

    if not student_name:
        student_name = input("Enter your name: ").strip()

    if not student_id:
        student_id = input("Enter your student ID: ").strip()

    if not student_name or not student_id:
        print("Error: Student name and ID are required")
        return 1

    # Create output filename
    # Replace spaces with underscores, remove special characters
    safe_name = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in student_name)
    output_name = f"{safe_name}_{student_id}"

    print("\n" + "="*60)
    print("LLM_ROBOT_2 Submission Package Creator")
    print("="*60)
    print(f"Student Name: {student_name}")
    print(f"Student ID: {student_id}")
    print(f"Output File: {output_name}.zip")
    print("="*60 + "\n")

    # Create packager
    packager = SubmissionPackager(project_root=args.project_root)

    # Collect files
    file_count = packager.collect_files()
    if file_count == 0:
        print("Error: No files found to package")
        return 1

    # Create ZIP
    zip_path = packager.create_zip(output_name, student_name, student_id)

    # Verify package
    if not packager.verify_package(zip_path):
        print("\n⚠️  Package verification failed")
        return 1

    print("\n" + "="*60)
    print("✓ SUBMISSION PACKAGE READY FOR SUBMISSION")
    print("="*60)
    print(f"File: {zip_path}")
    print(f"Size: {zip_path.stat().st_size / (1024*1024):.2f} MB")
    print("\nNext steps:")
    print("1. Verify the ZIP file contents")
    print("2. Test extraction and setup")
    print("3. Submit to your course platform")
    print("="*60)

    return 0


if __name__ == "__main__":
    exit(main())
