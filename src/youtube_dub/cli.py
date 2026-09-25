import argparse
import asyncio
import logging
import sys
import traceback

from youtube_dub.domain.errors import JobError, ManifestError
from youtube_dub.factory import create_studio_application


def main() -> None:
    parser = argparse.ArgumentParser(description="youtube-dub v3 CLI")
    parser.add_argument(
        "command",
        choices=["create", "run", "status", "resume", "cancel", "validate", "clean"],
    )
    parser.add_argument("--job-id", help="Job ID for operations", required=False)
    parser.add_argument("--source", help="Source language", default="en")
    parser.add_argument("--target", help="Target language", default="es")
    parser.add_argument("--media", help="Local media file for create", required=False)
    parser.add_argument("--url", help="YouTube URL for create", required=False)
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose debug logging"
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    try:
        studio = create_studio_application()
    except Exception as e:
        print(f"Failed to initialize application: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command == "create":
            manifest = studio.create_job(args.source, args.target)
            print(f"Created job {manifest.job_id}")
            if args.media:
                print(f"Ingesting local media from {args.media}...")
                studio.ingest_media(str(manifest.job_id), args.media)
            elif args.url:
                print(f"Downloading media from {args.url}...")
                studio.download_youtube_media(str(manifest.job_id), args.url)

        elif args.command == "run":
            if not args.job_id:
                print("--job-id is required for run", file=sys.stderr)
                sys.exit(1)

            async def run_and_wait():
                studio.run_job(args.job_id)
                print(f"Job {args.job_id} started. It is running in the background.")
                await studio._active_tasks[args.job_id]
                print(f"Job {args.job_id} finished.")

            asyncio.run(run_and_wait())

        elif args.command == "status":
            if not args.job_id:
                print("--job-id is required for status", file=sys.stderr)
                sys.exit(1)
            manifest = studio.get_job(args.job_id)
            print(f"Job ID: {manifest.job_id}")
            print(f"Status: {manifest.status.value}")
            print(f"Current Stage: {manifest.current_stage.value}")
            print(
                f"Source: {manifest.source_language}, Target: {manifest.target_language}"
            )

        elif args.command == "resume":
            if not args.job_id:
                print("--job-id is required for resume", file=sys.stderr)
                sys.exit(1)

            async def resume_and_wait():
                studio.resume_job(args.job_id)
                print(f"Job {args.job_id} resumed in background.")
                await studio._active_tasks[args.job_id]
                print(f"Job {args.job_id} finished.")

            asyncio.run(resume_and_wait())

        elif args.command == "cancel":
            if not args.job_id:
                print("--job-id is required for cancel", file=sys.stderr)
                sys.exit(1)
            studio.cancel_job(args.job_id)
            print(f"Job {args.job_id} cancellation requested.")

        elif args.command == "validate":
            if not args.job_id:
                print("--job-id is required for validate", file=sys.stderr)
                sys.exit(1)
            studio.validate_job(args.job_id)
            print(f"Job {args.job_id} validated successfully.")

        elif args.command == "clean":
            if not args.job_id:
                print("--job-id is required for clean", file=sys.stderr)
                sys.exit(1)
            studio.clean_job(args.job_id)
            print(f"Job {args.job_id} cleaned.")

        else:
            print(
                f"Command '{args.command}' not fully implemented yet.", file=sys.stderr
            )

    except (ManifestError, JobError) as e:
        if args.verbose:
            traceback.print_exc()
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
