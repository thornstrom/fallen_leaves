from fallen_leaves.cli import build_parser


def test_parses_ingest_trafikverket_defaults():
    args = build_parser().parse_args(["--catalog", "fallen_leaves_dev", "ingest-trafikverket"])

    assert args.catalog == "fallen_leaves_dev"
    assert args.lookback_days == 2
    assert args.operators == "SJ"


def test_parses_gold_root():
    args = build_parser().parse_args(["--catalog", "c", "gold", "--gold-root", "abfss://gold@x.dfs.core.windows.net/delta/"])

    assert args.gold_root.endswith("/delta/")
    assert args.max_lag == 2


def test_silver_full_flag():
    args = build_parser().parse_args(["--catalog", "c", "silver", "--full"])

    assert args.full is True
