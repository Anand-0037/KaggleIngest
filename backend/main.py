"""
Kaggle Notebook Ingestion Tool - Main Module
Refactored to use Service Layer pattern.
"""

import os
import sys
import uuid

# Import configuration and logging
try:
    from config import (
        DEFAULT_NOTEBOOKS,
        DEFAULT_OUTPUT_FILE,
        MAX_NOTEBOOKS,
        MIN_NOTEBOOKS,
    )
    from logger import get_logger, setup_logging
    # Initialize logging
    setup_logging()
    logger = get_logger(__name__)

    from core.exceptions import (
        KaggleIngestionError,
        NotebookDownloadError,
        URLParseError,
    )
    from core.utils import extract_resource
    from services.notebook_service import NotebookService

except ImportError as e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.error(f"Import error: {e}. Ensure you are running from the project root.")
    sys.exit(1)



def main():
    """Main CLI entry point."""
    print("=" * 60)
    print("Kaggle Notebook Ingestion Tool v4.0 (Services Architecture)")
    print("=" * 60)

    # 1. Credentials
    kaggle_creds = None
    if input("\nUse custom kaggle.json? (y/n, default n): ").strip().lower() == "y":
        cred_path = input("Path to kaggle.json: ").strip()
        if os.path.exists(cred_path):
            try:
                import json
                with open(cred_path) as f:
                    data = json.load(f)
                    kaggle_creds = {"username": data["username"], "key": data["key"]}
                print("✓ Custom credentials loaded")
            except Exception as e:
                print(f"✗ Error loading credentials: {e}")
        else:
            print(f"✗ File not found: {cred_path}")

    # 2. URL
    url = input("\nEnter Kaggle competition or dataset URL: ").strip()
    if not url:
        print("No URL provided. Exiting.")
        return

    try:
        resource = extract_resource(url)
        print(f"✓ Detected {resource['type']}: {resource['id']}")
    except URLParseError as e:
        print(f"✗ {e}")
        return

    # 3. Count
    try:
        count_input = input(
            f"\nEnter number of notebooks (default {DEFAULT_NOTEBOOKS}): "
        ).strip()
        top_n = int(count_input) if count_input else DEFAULT_NOTEBOOKS
        top_n = max(MIN_NOTEBOOKS, min(MAX_NOTEBOOKS, top_n))
    except ValueError:
        top_n = DEFAULT_NOTEBOOKS

    # 4. Language filter
    lang_input = input("\nFilter by language (python/r, default all): ").strip().lower()
    language = lang_input if lang_input in ["python", "r"] else None

    # 5. Format and Output File
    fmt = input("\nOutput format (txt/toon/md, default txt): ").strip().lower()

    slug = resource['id'].replace('/', '_')
    unique_id = uuid.uuid4().hex[:8]

    if fmt == "toon":
        output_format = "toon"
        output_file = f"context_{slug}_{unique_id}.toon"
    elif fmt == "md":
        output_format = "md"
        output_file = f"context_{slug}_{unique_id}.md"
    else:
        output_format = "txt"
        output_file = f"context_{slug}_{unique_id}.txt"

    # 6. Dry run
    dry_run = input("\nDry-run mode (validate only, no download)? (y/n, default n): ").strip().lower() == "y"

    # 7. Execution
    print(f"\n⏳ Fetching and processing top {top_n} notebooks...")

    try:
        service = NotebookService()
        result = service.get_completion_context(
            resource_type=resource['type'],
            identifier=resource['id'],
            top_n=top_n,
            kaggle_creds=kaggle_creds,
            language=language,
            dry_run=dry_run
        )

        # Format and Write Output
        content = service.format_output(result, format_type=output_format)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        stats = result["stats"]
        print(f"\n✓ Success! Output saved to: {output_file}")

        if not dry_run:
            print(f"  Downloaded: {stats.get('successful_downloads', 0)}")
            print(f"  Failed: {stats.get('failed_downloads', 0)}")
            print(f"  Time: {stats.get('elapsed_time', 0):.1f}s")
        else:
            print("  Dry run complete. Validated metadata.")

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        print(f"\n✗ Failed: {e}")
        # traceback.print_exc()

if __name__ == "__main__":
    main()
