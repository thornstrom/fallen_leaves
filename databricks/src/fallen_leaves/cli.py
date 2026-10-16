"""Ingångspunkt för Databricks python_wheel_task: ``fallen-leaves <steg> [flaggor]``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date


def _spark():
    from pyspark.sql import SparkSession

    return SparkSession.builder.getOrCreate()


def _layout(args):
    from fallen_leaves.config import Layout

    return Layout(args.catalog)


def cmd_ingest_trafikverket(args) -> None:
    from fallen_leaves.ingest import ingest_trafikverket

    api_key = os.environ.get("TRAFIKVERKET_API_KEY")
    if not api_key:
        sys.exit("TRAFIKVERKET_API_KEY saknas (sätts från secret scope i jobbet).")
    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    ingest_trafikverket(_layout(args), api_key, run_date, args.lookback_days, args.operators.split(","))


def cmd_ingest_smhi(args) -> None:
    from fallen_leaves.ingest import ingest_smhi

    ingest_smhi(_layout(args), args.since_days, [int(p) for p in args.parameters.split(",")])


def cmd_bronze(args) -> None:
    from fallen_leaves.bronze import load_all

    load_all(_spark(), _layout(args))


def cmd_silver(args) -> None:
    from fallen_leaves.pipeline import run_silver

    run_silver(_spark(), _layout(args), None if args.full else args.lookback_days)


def cmd_gold(args) -> None:
    from fallen_leaves.pipeline import run_gold

    run_gold(_spark(), _layout(args), args.gold_root.rstrip("/"), args.max_lag)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fallen-leaves")
    p.add_argument("--catalog", required=True)
    sub = p.add_subparsers(dest="command", required=True)

    tv = sub.add_parser("ingest-trafikverket")
    tv.add_argument("--run-date", help="ÅÅÅÅ-MM-DD, standard idag")
    tv.add_argument("--lookback-days", type=int, default=2)
    tv.add_argument("--operators", default="SJ", help="Kommaseparerad lista")
    tv.set_defaults(func=cmd_ingest_trafikverket)

    sm = sub.add_parser("ingest-smhi")
    sm.add_argument("--since-days", type=int, default=3)
    sm.add_argument("--parameters", default="1,7")
    sm.set_defaults(func=cmd_ingest_smhi)

    br = sub.add_parser("bronze")
    br.set_defaults(func=cmd_bronze)

    si = sub.add_parser("silver")
    si.add_argument("--lookback-days", type=int, default=7)
    si.add_argument("--full", action="store_true", help="Bearbeta hela bronze")
    si.set_defaults(func=cmd_silver)

    go = sub.add_parser("gold")
    go.add_argument("--gold-root", required=True, help="abfss://gold@<konto>.dfs.core.windows.net/delta")
    go.add_argument("--max-lag", type=int, default=2)
    go.set_defaults(func=cmd_gold)
    return p


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
