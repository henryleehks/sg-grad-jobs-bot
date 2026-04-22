from __future__ import annotations

import argparse

from sg_grad_jobs_bot.sources import fetch_jobs, format_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch SG fresh grad SE/DevOps jobs")
    parser.add_argument("--days-back", type=int, default=14)
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()

    jobs = fetch_jobs(days_back=args.days_back, max_results=args.max_results)
    print(format_jobs(jobs))


if __name__ == "__main__":
    main()
