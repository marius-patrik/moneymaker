"""moneymaker — provider-agnostic paper/live trading engine."""

try:
    from importlib.metadata import version, PackageNotFoundError
    __version__ = version("moneymaker")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"
