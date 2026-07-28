import argparse

from analyzer.config import DEFAULT_GEMINI_MODEL, DEFAULT_INPUT_FILE, DEFAULT_OUTPUT_DIR
from analyzer.pipeline import process_teams


def build_parser():
    parser = argparse.ArgumentParser(description='Git Repository Commit Analysis Tool')
    parser.add_argument('--input', default=DEFAULT_INPUT_FILE,
                         help=f'CSV file with student_name,repo_url[,github_username] (default: {DEFAULT_INPUT_FILE})')
    parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR,
                         help=f'Directory to write per-student reports to (default: {DEFAULT_OUTPUT_DIR})')
    parser.add_argument('--model', default=DEFAULT_GEMINI_MODEL,
                         help=f'Gemini model to use for AI analysis (default: {DEFAULT_GEMINI_MODEL})')
    parser.add_argument('--skip-ai', action='store_true',
                         help='Skip Gemini AI analysis (rule-based warnings, charts and CSV still generated)')
    parser.add_argument('--workers', type=int, default=4,
                         help='Number of students to process concurrently (default: 4; use 1 for sequential)')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    print("Starting Git Commits Analysis Tool")
    print("=" * 80)
    process_teams(
        args.input,
        output_dir=args.output_dir,
        model_name=args.model,
        skip_ai=args.skip_ai,
        workers=args.workers,
    )
    print("\n" + "=" * 80)
    print("All processing completed!")
    print("=" * 80)


if __name__ == '__main__':
    main()
