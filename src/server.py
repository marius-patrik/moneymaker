"""FastAPI server. API lives under /api. Serves the built React SPA from ui/dist/ when present."""

from __future__ import annotations

import csv
import datetime as dt
import logging
import os
import pathlib
import threading
import uuid
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.accounts import AccountManager, CredentialStore

log = logging.getLogger(__name__)
from src.data import DataFeed
from src.engine import Simulator
from src.jobs import JobManager
from src.logger import TradeLogger
from src.multiwindow import run_multi_window_backtest
from src.optimizer import default_objective, grid_search
from src.providers import PROVIDERS, make_provider
from src.providers.simulated import SimulatedExecutionProvider
from src.risk import RiskManager
from src.strategy import BUILTIN_STRATEGIES, load_strategies


# ---------------------------------------------------------------------------
# Shared server state (one instance per process)
# ---------------------------------------------------------------------------

class ServerState:
    def __init__(self, home: str):
        self.home = home
        self.sessions: dict[str, Simulator] = {}
        self.lock = threading.Lock()
        self.jobs = JobManager()
        self.monitor_stop = threading.Event()
        self.last_sweep: Optional[str] = None
        self.sweep_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class CreateAccountBody(BaseModel):
    name: str
    provider: str = "simulated"
    currency: str = "USD"
    starting_balance: float = 10000.0
    is_live: bool = False


class SetCredentialBody(BaseModel):
    provider: str
    key: str
    env_var: Optional[str] = None
    value: Optional[str] = None


class BacktestBody(BaseModel):
    strategy: str
    ticker: str
    start: str
    end: str
    interval: str = "5m"
    provider: str = "simulated"
    account_id: Optional[str] = None
    account: float = 10000.0
    risk_pct: float = 0.01
    params: dict[str, Any] = {}
    data_provider: str = "yfinance"
    data_provider_path: Optional[str] = None


class LiveStartBody(BaseModel):
    strategy: str
    ticker: str
    provider: str = "simulated"
    account_id: Optional[str] = None
    account: float = 10000.0
    risk_pct: float = 0.01
    end_time: str = "11:00"
    poll_seconds: int = 30


class BacktestMultiBody(BaseModel):
    strategy: str
    ticker: str
    windows: list[list[str]]  # [[start, end], ...]
    interval: str = "5m"
    provider: str = "simulated"
    account: float = 10000.0
    risk_pct: float = 0.01


class ForkEvalBody(BaseModel):
    strategy: str
    ticker: str
    windows: list[list[str]]
    interval: str = "5m"
    provider: str = "simulated"
    account: float = 10000.0
    risk_pct: float = 0.01


class EvolveBody(BaseModel):
    strategy: str
    ticker: str
    windows: list[list[str]]
    interval: str = "5m"
    provider: str = "simulated"
    account: float = 10000.0
    risk_pct: float = 0.01
    generations: int = 20
    perturbation: float = 0.20
    start_params: Optional[dict[str, Any]] = None


class SetHomeBody(BaseModel):
    home: str


class PendingOrderBody(BaseModel):
    ticker: str
    direction: str                     # "long" | "short"
    size: float
    order_type: str                    # limit | stop | stop_loss | take_profit
    trigger_price: float
    limit_price: Optional[float] = None
    account_id: Optional[str] = None
    position_id: Optional[str] = None  # for protective exits


class ManualOrderBody(BaseModel):
    ticker: str
    direction: str                     # "long" | "short"
    size: float
    account_id: Optional[str] = None
    provider: str = "simulated"
    closing: bool = False
    reference_price: Optional[float] = None   # omitted → fetch the last price
    data_provider: str = "yfinance"
    # Attached at entry, the way a broker's ticket does it.
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class CreateStrategyBody(BaseModel):
    name: str
    source: str = ""          # empty → start from the template below
    overwrite: bool = False


# Starting point for a strategy created from the UI. Mirrors
# strategies/example_momentum.py, trimmed to the parts worth editing.
_STRATEGY_TEMPLATE = '''"""Created from the moneymaker UI."""

from src.strategy import Bar, Strategy, StrategyContext


class __CLASS__(Strategy):
    """One-line description — this shows up in the strategy list."""

    name = "__NAME__"

    def __init__(self, stop_pct: float = 0.005, target_pct: float = 0.010):
        # Every __init__ argument with a default becomes a tunable parameter
        # in the UI and on the CLI via --param.
        self.stop_pct = stop_pct
        self.target_pct = target_pct

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        # Manage an open position first.
        if ctx.position_open:
            change = (bar.price - ctx.entry_price) / ctx.entry_price
            if change >= self.target_pct:
                ctx.extra["close_reason"] = "target"
                ctx.extra["close_now"] = True
            elif change <= -self.stop_pct:
                ctx.extra["close_reason"] = "stop"
                ctx.extra["close_now"] = True
            return

        # Entry logic goes here. This example takes one long trade on the
        # first bar so the strategy does something runnable out of the box.
        if ctx.trades_taken >= 1:
            return

        ctx.position_open = True
        ctx.direction = "long"
        ctx.entry_price = bar.price
        ctx.entry_time = bar.time
        ctx.stop_price = bar.price * (1 - self.stop_pct)
        ctx.target_price = bar.price * (1 + self.target_pct)
'''


class OptimizeBody(BaseModel):
    strategy: str
    ticker: str
    param_grid: dict[str, list[Any]]
    train_windows: list[list[str]]
    test_windows: Optional[list[list[str]]] = None
    interval: str = "5m"
    provider: str = "simulated"
    account: float = 10000.0
    risk_pct: float = 0.01


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Names traders use that Yahoo's search does not resolve, mapped to the
# nearest instrument it actually carries. The note is shown in the UI so the
# substitution is never silent.
INSTRUMENT_ALIASES: dict[str, list[tuple[str, str, str, str]]] = {
    "xauusd": [
        ("GC=F", "Gold futures", "future", "Yahoo has no spot gold — this is the front-month future"),
        ("PAXG-USD", "PAX Gold", "cryptocurrency", "Tokenised gold, tracks spot closely"),
        ("GLD", "SPDR Gold Shares", "etf", "Gold ETF"),
    ],
    "xagusd": [
        ("SI=F", "Silver futures", "future", "Yahoo has no spot silver — front-month future"),
        ("SLV", "iShares Silver Trust", "etf", "Silver ETF"),
    ],
    "xptusd": [("PL=F", "Platinum futures", "future", "Front-month future")],
    "wti": [("CL=F", "Crude Oil WTI futures", "future", "")],
    "brent": [("BZ=F", "Brent Crude futures", "future", "")],
    "natgas": [("NG=F", "Natural Gas futures", "future", "")],
    "spx": [("^GSPC", "S&P 500 Index", "index", ""), ("ES=F", "E-mini S&P 500", "future", "")],
    "nas100": [("^NDX", "Nasdaq 100 Index", "index", ""), ("NQ=F", "E-mini Nasdaq 100", "future", "")],
    "us30": [("^DJI", "Dow Jones Industrial Average", "index", ""), ("YM=F", "E-mini Dow", "future", "")],
    "ger40": [("^GDAXI", "DAX Index", "index", "")],
    "uk100": [("^FTSE", "FTSE 100 Index", "index", "")],
}


def _mark_open(home: str, account_id: Optional[str] = None) -> tuple[list[dict], float]:
    """
    Open manual positions marked to market, plus their total unrealised P&L.

    Headline figures counted realised P&L only, so an open position was
    invisible in every total — the account could be deep in a losing trade
    and the dashboard would show it flat.
    """
    from src.book import ManualBook
    from src.data_providers import make_data_provider

    rows = ManualBook(home).list(account_id)
    if not rows:
        return [], 0.0

    prov = make_data_provider("yfinance", home)
    marks: dict[str, Optional[float]] = {}
    total = 0.0
    out = []
    for pos in rows:
        tk = pos["ticker"]
        if tk not in marks:
            try:
                marks[tk] = prov.get_last_price(tk)[0]
            except Exception:
                marks[tk] = None      # a quote failure must not hide the position
        mark = marks[tk]
        unreal = None
        if mark is not None:
            sign = 1 if pos["direction"] == "long" else -1
            unreal = round(sign * (mark - pos["entry_price"]) * pos["size"], 2)
            total += unreal
        out.append({**pos, "mark": mark, "unrealised_pnl": unreal})
    return out, round(total, 2)


def _num(v: Optional[str]) -> Optional[float]:
    """Parse a CSV numeric cell, tolerating blanks and junk."""
    if v in (None, ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def make_app(home: str, ui_dist: Optional[pathlib.Path] = None) -> FastAPI:
    """
    Build the app. `ui_dist` overrides where the built SPA is found, which
    lets tests exercise the fallback without depending on a real UI build.
    """
    state = ServerState(home)
    app = FastAPI(title="moneymaker", version="0.4.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValueError)
    def _value_error(request: Request, exc: ValueError):
        """
        Turn bad-input errors into JSON 400s.

        The engine signals unusable input with ValueError — an unknown
        ticker, a range with no bars, an interval the provider will not
        serve. Unhandled, FastAPI returns a 500 whose body is the plain
        string "Internal Server Error", so a client cannot parse a message
        out of it and the user sees nothing at all.
        """
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    api = APIRouter(prefix="/api")

    # ---- helpers ----

    def _resolve_account(provider, account_id: Optional[str], account: float) -> str:
        if account_id:
            return account_id
        accts = provider.list_accounts()
        if accts:
            return accts[0].account_id
        return provider.create_account("default", starting_balance=account).account_id

    def _status_payload(sim: Simulator) -> dict:
        """Simulator.status() with the summary metrics lifted to the top level.

        status() nests trade metrics under "summary"; clients want them flat.
        The nested "summary" is kept so nothing is lost.
        """
        st = sim.status()
        summary = st.get("summary") or {}
        return {
            **st,
            "running": not sim.stopped.is_set(),
            "trade_count": summary.get("trades", 0),
            "total_pnl": summary.get("total_pnl", 0.0),
            "win_rate": summary.get("win_rate", 0.0),
        }

    # ---- strategies ----

    def _jsonable(v: Any) -> Any:
        """Coerce param defaults (time, date, etc.) into JSON-serialisable values."""
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        return str(v)

    @api.get("/strategies")
    def list_strategies():
        """
        Every strategy, all of them the user's to edit.

        The ones in the repo are starting points that get copied into the
        data directory on install — not a privileged class — so no
        provenance is reported. `editable` says whether a file exists to
        edit, which is the only distinction that affects what you can do.
        """
        strategies = load_strategies(state.home)
        return {"strategies": [
            {
                "name": n,
                "doc": (c.__doc__ or "").strip().split("\n")[0],
                "editable": (pathlib.Path(state.home) / "strategies" / f"{n}.py").is_file(),
                "params": {k: _jsonable(v) for k, v in c.params().items()}
                          if hasattr(c, "params") else {},
            }
            for n, c in strategies.items()
        ]}

    @api.get("/strategies/stats")
    def strategy_stats():
        """
        Per-strategy performance, read from the session logs.

        Session files are named <kind>_<strategy>_<detail>, so a run can be
        attributed to the strategy that produced it without extra bookkeeping.
        """
        names = sorted(load_strategies(state.home), key=len, reverse=True)
        sess = pathlib.Path(state.home) / "sessions"
        agg: dict[str, dict] = {}

        if sess.is_dir():
            for path in sess.glob("*.csv"):
                stem = path.stem
                owner = next((n for n in names if n in stem), None)
                if not owner:
                    continue
                try:
                    with open(path) as f:
                        rows = list(csv.DictReader(f))
                except OSError:
                    continue
                a = agg.setdefault(owner, {"runs": 0, "pnls": [], "last": ""})
                a["runs"] += 1
                mtime = dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                    timespec="seconds")
                a["last"] = max(a["last"], mtime)
                for r in rows:
                    v = _num(r.get("pnl"))
                    if v is not None:
                        a["pnls"].append(v)

        out = {}
        for name, a in agg.items():
            pnls = a["pnls"]
            wins = [v for v in pnls if v > 0]
            losses = [v for v in pnls if v < 0]
            out[name] = {
                "runs": a["runs"],
                "trades": len(pnls),
                "total_pnl": round(sum(pnls), 2),
                "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
                "profit_factor": (round(sum(wins) / abs(sum(losses)), 2)
                                  if losses and sum(losses) else None),
                "best": round(max(pnls), 2) if pnls else None,
                "worst": round(min(pnls), 2) if pnls else None,
                "last_run": a["last"],
            }
        return {"stats": out}

    @api.post("/strategies/{name}/duplicate")
    def duplicate_strategy(name: str, new_name: Optional[str] = None):
        """
        Copy a strategy into the data directory so it can be edited.

        Strategies defined in code have no file to open; duplicating one
        writes a subclass that inherits the behaviour and exposes it for
        editing, so nothing in the app is off-limits to the user.
        """
        strategies = load_strategies(state.home)
        cls = strategies.get(name)
        if not cls:
            raise HTTPException(404, f"unknown strategy: {name}")

        target = (new_name or f"{name}_copy").strip()
        if not target.isidentifier():
            raise HTTPException(400, "name must be a valid Python identifier")

        dest = pathlib.Path(state.home) / "strategies" / f"{target}.py"
        if dest.exists():
            raise HTTPException(409, f"'{target}' already exists")

        src_file = pathlib.Path(state.home) / "strategies" / f"{name}.py"
        if src_file.is_file():
            source = src_file.read_text().replace(f'name = "{name}"', f'name = "{target}"')
        else:
            # Defined in code — subclass it so the copy is editable.
            source = (
                f'"""Copy of {name}, editable."""\n\n'
                f"from {cls.__module__} import {cls.__name__}\n\n\n"
                f"class {cls.__name__}Copy({cls.__name__}):\n"
                f'    """Edit freely — this is your copy of {name}."""\n\n'
                f'    name = "{target}"\n'
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(source)
        if target not in load_strategies(state.home):
            dest.unlink(missing_ok=True)
            raise HTTPException(400, f"copy did not register as '{target}'")
        return {"name": target, "path": str(dest)}

    @api.get("/strategies/{name}/source")
    def get_strategy_source(name: str):
        """Source of a user strategy, for editing in the UI."""
        path = pathlib.Path(state.home) / "strategies" / f"{name}.py"
        if not path.is_file():
            raise HTTPException(404, f"no editable source for '{name}'")
        return {"name": name, "source": path.read_text(), "path": str(path)}

    @api.post("/strategies")
    def create_strategy(body: CreateStrategyBody):
        """
        Write a strategy into <home>/strategies/, where it is auto-loaded.

        Saving invalid Python would make the strategy list warn on every
        request, so the source is compiled first and rejected if it does not
        parse or defines no Strategy subclass.
        """
        safe = body.name.strip()
        if not safe.isidentifier():
            raise HTTPException(
                400, "name must be a valid Python identifier (letters, digits, underscore)")

        source = body.source.strip() or _STRATEGY_TEMPLATE.replace("__NAME__", safe).replace(
            "__CLASS__", "".join(p.title() for p in safe.split("_")))

        try:
            compile(source, f"{safe}.py", "exec")
        except SyntaxError as e:
            raise HTTPException(400, f"syntax error on line {e.lineno}: {e.msg}")
        if "Strategy" not in source:
            raise HTTPException(400, "source defines no Strategy subclass")

        path = pathlib.Path(state.home) / "strategies" / f"{safe}.py"
        if path.exists() and not body.overwrite:
            raise HTTPException(409, f"'{safe}' already exists — set overwrite to replace it")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)

        # Confirm it actually loads, so a strategy that imports something
        # missing is reported now rather than silently absent from the list.
        if safe not in load_strategies(state.home):
            path.unlink(missing_ok=True)
            raise HTTPException(
                400, f"saved source did not register a strategy named '{safe}' — "
                     "check the class's `name` attribute")
        return {"name": safe, "path": str(path)}

    @api.delete("/strategies/{name}")
    def delete_strategy(name: str):
        path = pathlib.Path(state.home) / "strategies" / f"{name}.py"
        if not path.is_file():
            raise HTTPException(404, f"no user strategy named '{name}'")
        path.unlink()
        return {"deleted": name}

    # ---- providers ----

    @api.get("/providers")
    def list_providers(include_stubs: bool = False):
        """
        Providers grouped by what they supply: market data, economic
        calendar/news, and order execution.

        Scaffolded-but-unimplemented execution providers are omitted unless
        include_stubs is set — they cannot do anything yet, so listing them
        by default just implies capability that is not there.
        """
        def _doc(cls) -> str:
            return (cls.__doc__ or "").strip().split("\n")[0]

        execution = [
            {"name": n, "doc": _doc(c),
             "status": "ready" if c is SimulatedExecutionProvider else "stub",
             "is_live": bool(getattr(c, "is_live", False))}
            for n, c in PROVIDERS.items()
        ]
        if not include_stubs:
            execution = [p for p in execution if p["status"] == "ready"]

        from src.data_providers import DATA_PROVIDERS
        data = [
            {"name": n, "doc": _doc(c), "status": "ready",
             "is_live": bool(getattr(c, "is_live", False))}
            for n, c in DATA_PROVIDERS.items()
        ]

        # Calendar sources are constructed per series rather than registered
        # in a dict, so they are described here.
        news = [
            {"name": "fred", "status": "ready",
             "doc": "US economic release dates via FRED vintage dates (API key required)."},
            {"name": "simulated", "status": "ready",
             "doc": "In-memory fixture calendar; no network."},
            {"name": "bls", "status": "stub",
             "doc": "BLS offers no clean vintage-date API — use a FRED equivalent."},
        ]
        if not include_stubs:
            news = [p for p in news if p["status"] == "ready"]

        return {"data": data, "news": news, "execution": execution,
                # Kept so existing clients that read `providers` still work.
                "providers": execution}

    # ---- accounts ----

    @api.get("/accounts")
    def list_accounts():
        mgr = AccountManager(state.home)
        return {"accounts": [a.to_dict() for a in mgr.list()]}

    @api.get("/accounts/{account_id}")
    def get_account(account_id: str):
        mgr = AccountManager(state.home)
        info = mgr.get(account_id)
        if not info:
            raise HTTPException(404, "not found")
        return info.to_dict()

    @api.post("/accounts")
    def create_account(body: CreateAccountBody):
        mgr = AccountManager(state.home)
        a = mgr.create(body.name, body.provider, currency=body.currency,
                       starting_balance=body.starting_balance, is_live=body.is_live)
        return a.to_dict()

    @api.post("/accounts/prune")
    def prune_accounts(prefix: str = "mw_", dry_run: bool = True):
        """Clean up scratch accounts left by older multi-window backtests."""
        mgr = AccountManager(state.home)
        matched = mgr.prune(prefix=prefix, dry_run=dry_run)
        return {"matched": len(matched), "deleted": 0 if dry_run else len(matched),
                "dry_run": dry_run,
                "sample": [a.name for a in matched[:5]]}

    @api.delete("/accounts/{account_id}")
    def delete_account(account_id: str):
        mgr = AccountManager(state.home)
        if not mgr.get(account_id):
            raise HTTPException(404, "not found")
        mgr.delete(account_id)
        return {"deleted": account_id}

    # ---- credentials ----

    @api.get("/credentials")
    def list_credentials():
        store = CredentialStore(state.home)
        return {"credentials": store.list_masked()}

    @api.post("/credentials")
    def set_credential(body: SetCredentialBody):
        store = CredentialStore(state.home)
        if body.env_var:
            store.set_ref(body.provider, body.key, body.env_var)
        elif body.value:
            store.set_value(body.provider, body.key, body.value)
        else:
            raise HTTPException(400, "provide env_var (recommended) or value")
        return {"ok": True}

    @api.delete("/credentials/{provider}")
    def clear_credential(provider: str, key: Optional[str] = None):
        CredentialStore(state.home).clear(provider, key)
        return {"cleared": provider, "key": key}

    # ---- sessions ----

    @api.get("/sessions")
    def list_sessions(limit: int = 200):
        """
        Sessions newest-first, each with a summary read from its trades.

        A bare filename tells you almost nothing, so every CSV is scanned for
        trade count, P&L and win rate. Files are small (one row per trade)
        and the newest `limit` are read, so this stays cheap.
        """
        sess_dir = pathlib.Path(state.home) / "sessions"
        if not sess_dir.is_dir():
            return {"sessions": []}

        files = sorted(sess_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        out = []
        for path in files[:limit]:
            entry = {
                "name": path.name,
                "kind": "trades" if path.suffix == ".csv" else "result",
                "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                    timespec="seconds"),
                "size": path.stat().st_size,
            }
            if path.suffix == ".csv":
                try:
                    with open(path) as f:
                        rows = list(csv.DictReader(f))
                    pnls = [float(r["pnl"]) for r in rows
                            if r.get("pnl") not in (None, "")]
                    wins = [p for p in pnls if p > 0]
                    entry.update({
                        "trades": len(pnls),
                        "total_pnl": round(sum(pnls), 2),
                        "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
                        "ticker": rows[0].get("ticker") if rows else None,
                        "first_trade": rows[0].get("entry_time") if rows else None,
                        "last_trade": rows[-1].get("exit_time") if rows else None,
                    })
                except (OSError, ValueError, KeyError):
                    # A malformed or half-written log should not break the list.
                    entry["trades"] = None
            out.append(entry)
        return {"sessions": out}

    @api.get("/sessions/{filename}")
    def get_session(filename: str):
        path = os.path.join(state.home, "sessions", filename)
        if not os.path.exists(path):
            raise HTTPException(404, "not found")
        if filename.endswith(".csv"):
            with open(path) as f:
                return {"trades": list(csv.DictReader(f))}
        import json
        with open(path) as f:
            return json.load(f)

    # ---- backtest ----

    @api.post("/backtest")
    def run_backtest(body: BacktestBody):
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")
        from src.data_providers import make_data_provider
        kwargs = {"path": body.data_provider_path} if body.data_provider_path else {}
        data_prov = make_data_provider(body.data_provider, state.home, **kwargs)
        df = data_prov.get_historical(body.ticker, body.start, body.end, interval=body.interval)
        strategy = strategy_cls(**body.params)
        provider = make_provider(body.provider, state.home)
        account_id = _resolve_account(provider, body.account_id, body.account)
        risk = RiskManager(risk_pct=body.risk_pct)
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        logger = TradeLogger(state.home, f"backtest_{body.strategy}_{ts}")
        sim = Simulator(strategy, provider, account_id, risk, logger, ticker=body.ticker)
        sim.run_backtest(df)
        return {"session_name": logger.session_name, "account_id": account_id, **_status_payload(sim)}

    # ---- backtest-multi ----

    @api.post("/backtest-multi")
    def run_backtest_multi(body: BacktestMultiBody):
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")
        windows = [tuple(w) for w in body.windows]
        result = run_multi_window_backtest(
            strategy_factory=strategy_cls, provider_name=body.provider, home=state.home,
            ticker=body.ticker, windows=windows, interval=body.interval,
            account_balance=body.account, risk_pct=body.risk_pct,
        )
        return result.to_dict()

    # ---- optimize ----

    @api.post("/optimize")
    def run_optimize(body: OptimizeBody, background: bool = True):
        """
        Grid-search the parameter space. Cost is the product of the grid
        sizes times the window count, so this is a job by default.
        """
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")
        train_windows = [tuple(w) for w in body.train_windows]
        test_windows = [tuple(w) for w in body.test_windows] if body.test_windows else None

        def _work(_job=None):
            return grid_search(
                strategy_cls=strategy_cls, param_grid=body.param_grid,
                provider_name=body.provider, home=state.home,
                ticker=body.ticker, train_windows=train_windows,
                test_windows=test_windows, interval=body.interval,
                account_balance=body.account, risk_pct=body.risk_pct,
            ).to_dict(default_objective)

        if not background:
            return _work()
        combos = 1
        for values in body.param_grid.values():
            combos *= max(1, len(values))
        job = state.jobs.submit(
            "optimize", f"{body.strategy} · {body.ticker} · {combos} combos", _work)
        return job.to_dict()

    # ---- agents: fork-eval, evolve, rankings ----

    def _resolve_forks(strategy_cls, strategies: dict) -> list:
        """Resolve a strategy's FORKS entries to (label, cls, params) triples."""
        raw = getattr(strategy_cls, "FORKS", None)
        if not raw:
            raise HTTPException(
                400, f"strategy '{strategy_cls.name}' declares no FORKS")
        forks = []
        for label, strat_name, params in raw:
            cls = strategies.get(strat_name)
            if not cls:
                raise HTTPException(
                    400, f"fork '{label}' references unknown strategy '{strat_name}'")
            forks.append((label, cls, params))
        return forks

    @api.post("/fork-eval")
    def run_fork_eval(body: ForkEvalBody, background: bool = True):
        """
        Evaluate a strategy's FORKS. Runs one backtest per fork per window,
        so it goes through the job queue by default; pass background=false
        to block on the result instead.
        """
        from src.agents.forker import fork_and_eval
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")
        forks = _resolve_forks(strategy_cls, strategies)

        def _work(_job=None):
            return fork_and_eval(
                forks=forks, provider_name=body.provider, home=state.home,
                ticker=body.ticker, windows=[tuple(w) for w in body.windows],
                interval=body.interval, account_balance=body.account,
                risk_pct=body.risk_pct,
            ).to_dict()

        if not background:
            return _work()
        job = state.jobs.submit("fork-eval", f"{body.strategy} · {body.ticker}", _work)
        return job.to_dict()

    @api.post("/evolve")
    def run_evolve(body: EvolveBody, background: bool = True):
        """
        Hill-climb the strategy's numeric parameters. One full backtest per
        generation — always slow, so this is a job by default.
        """
        from src.agents.evolution import evolve
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")

        def _work(_job=None):
            return evolve(
                strategy_cls=strategy_cls, provider_name=body.provider,
                home=state.home, ticker=body.ticker,
                windows=[tuple(w) for w in body.windows],
                start_params=body.start_params, max_generations=body.generations,
                perturbation_pct=body.perturbation, interval=body.interval,
                account_balance=body.account, risk_pct=body.risk_pct,
            ).to_dict()

        if not background:
            return _work()
        job = state.jobs.submit(
            "evolve", f"{body.strategy} · {body.ticker} · {body.generations}gen", _work)
        return job.to_dict()

    # ---- manual trading ----

    @api.get("/quote/{ticker:path}")
    def get_quote(ticker: str, data_provider: str = "yfinance"):
        """Last price for a ticker, for the manual ticket."""
        from src.data_providers import make_data_provider
        prov = make_data_provider(data_provider, state.home)
        if not getattr(prov, "is_live", False):
            raise HTTPException(400, f"'{data_provider}' does not provide live prices")
        price, ts = prov.get_last_price(ticker)
        return {"ticker": ticker, "price": price,
                "time": ts.isoformat() if hasattr(ts, "isoformat") else str(ts)}

    @api.get("/search")
    def search_instruments(q: str, limit: int = 12):
        """
        Instrument search.

        Yahoo's index misses names traders actually use — searching
        "XAUUSD" returns nothing, because Yahoo carries no spot metals at
        all. ALIASES map those names to the nearest instrument that does
        exist and say so, rather than leaving the search empty. A literal
        symbol is also probed directly, so a known ticker always resolves.
        """
        query = q.strip()
        if not query:
            return {"results": []}

        results: list[dict] = []
        seen: set[str] = set()

        def add(symbol: str, name: str, kind: str, exchange: str, note: str = ""):
            if symbol and symbol not in seen:
                seen.add(symbol)
                results.append({"symbol": symbol, "name": name,
                                "type": kind, "exchange": exchange, "note": note})

        for sym, name, kind, note in INSTRUMENT_ALIASES.get(query.lower().replace("/", ""), []):
            add(sym, name, kind, "", note)

        try:
            import yfinance as yf
            for h in (yf.Search(query, max_results=min(limit, 25)).quotes or []):
                add(h.get("symbol"), h.get("shortname") or h.get("longname") or "",
                    (h.get("quoteType") or "").lower(), h.get("exchange") or "")
        except Exception:
            pass    # aliases and the literal probe below may still answer

        # An exact symbol the index does not surface should still resolve.
        if not results and query.upper() == query.replace(" ", ""):
            try:
                import yfinance as yf
                probe = yf.Ticker(query.upper())
                if probe.fast_info.last_price:
                    add(query.upper(), "", "", "")
            except Exception:
                pass

        if not results:
            raise HTTPException(
                404,
                f"No instrument matches '{query}'. Yahoo carries no spot FX metals "
                f"— try the futures contract (GC=F for gold, SI=F for silver) or an ETF.")
        return {"results": results[:limit]}

    @api.get("/history/{ticker:path}")
    def get_history(ticker: str, interval: str = "1h", days: int = 30,
                    data_provider: str = "yfinance"):
        """
        OHLCV candles for the chart.

        Full bars rather than closes: a candle carries the range and the
        direction of each period, which a line hides. Times are emitted as
        UNIX seconds because that is what the charting library indexes on.
        """
        from src.data_providers import make_data_provider
        end = dt.datetime.now()
        start = end - dt.timedelta(days=max(1, days))
        prov = make_data_provider(data_provider, state.home)
        df = prov.get_historical(ticker, start.strftime("%Y-%m-%d"),
                                 end.strftime("%Y-%m-%d"), interval=interval)
        if df is None or len(df) == 0:
            raise HTTPException(400, f"no bars for {ticker} at {interval}")

        def col(name: str):
            return df[name] if name in df.columns else None

        o, h, l, c, v = (col("Open"), col("High"), col("Low"),
                         col("Close"), col("Volume"))
        if c is None:
            raise HTTPException(400, f"no close prices for {ticker}")

        candles = []
        for i, idx in enumerate(df.index):
            close = float(c.iloc[i])
            if close != close:          # NaN
                continue
            def at(series, fallback):
                if series is None:
                    return fallback
                val = float(series.iloc[i])
                return fallback if val != val else val
            ts = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            candles.append({
                "time": int(ts.timestamp()),
                "open": at(o, close), "high": at(h, close),
                "low": at(l, close), "close": close,
                "volume": at(v, 0.0),
            })

        if not candles:
            raise HTTPException(400, f"no usable bars for {ticker}")

        closes = [b["close"] for b in candles]
        first, last = closes[0], closes[-1]
        return {
            "ticker": ticker,
            "interval": interval,
            "candles": candles,
            "last": last,
            "change": round(last - first, 4),
            "change_pct": round(last / first - 1, 6) if first else 0.0,
            "high": max(b["high"] for b in candles),
            "low": min(b["low"] for b in candles),
        }

    @api.get("/news")
    def get_news(q: str = "markets", limit: int = 20):
        """
        Headlines for an instrument or topic.

        Release *dates* come from the economic calendar; this is the
        narrative around them, which is what a discretionary read needs and
        the calendar cannot give.
        """
        try:
            import yfinance as yf
            items = yf.Search(q.strip() or "markets",
                              news_count=min(limit, 50)).news or []
        except Exception as e:
            raise HTTPException(502, f"news unavailable: {e}")

        out = []
        for n in items:
            published = n.get("providerPublishTime")
            out.append({
                "title": n.get("title") or "",
                "publisher": n.get("publisher") or "",
                "link": n.get("link") or "",
                "published": (dt.datetime.fromtimestamp(published).isoformat(timespec="seconds")
                              if published else ""),
                "tickers": n.get("relatedTickers") or [],
                "thumbnail": (((n.get("thumbnail") or {}).get("resolutions") or [{}])[0]
                              .get("url", "")),
            })
        out.sort(key=lambda x: x["published"], reverse=True)
        return {"query": q, "items": out}

    @api.get("/quick-search")
    def quick_search(q: str, limit: int = 8):
        """
        One search across everything: instruments, strategies, accounts and
        recorded runs.

        The palette used to search only pages and strategy names, so finding
        an instrument or a past run meant knowing which screen to visit first.
        """
        query = q.strip().lower()
        if not query:
            return {"groups": []}

        groups: list[dict] = []

        strategies = [
            {"id": n, "label": n, "sub": (c.__doc__ or "").strip().split("\n")[0][:60],
             "route": "/strategies"}
            for n, c in load_strategies(state.home).items()
            if query in n.lower()
        ][:limit]
        if strategies:
            groups.append({"group": "Systems", "items": strategies})

        accounts = [
            {"id": a.account_id, "label": a.name,
             "sub": f"{a.provider} · {a.balance:,.2f}", "route": "/portfolio"}
            for a in AccountManager(state.home).list()
            if query in a.name.lower() or query in a.account_id.lower()
        ][:limit]
        if accounts:
            groups.append({"group": "Accounts", "items": accounts})

        sess_dir = pathlib.Path(state.home) / "sessions"
        if sess_dir.is_dir():
            runs = [
                {"id": p.name, "label": p.stem, "sub": "recorded run", "route": "/portfolio"}
                for p in sorted(sess_dir.glob("*.csv"),
                                key=lambda x: x.stat().st_mtime, reverse=True)
                if query in p.stem.lower()
            ][:limit]
            if runs:
                groups.append({"group": "History", "items": runs})

        try:
            found = search_instruments(q, limit=limit)["results"]
            if found:
                groups.append({"group": "Instruments", "items": [
                    {"id": r["symbol"], "label": r["symbol"],
                     "sub": r.get("note") or r["name"], "route": "/trade"}
                    for r in found
                ]})
        except HTTPException:
            pass    # no instrument match is not an error for a mixed search

        return {"groups": groups}

    @api.get("/indicators")
    def list_indicators():
        """What the chart can overlay, and each one's default."""
        from src.indicators import CATALOG
        return {"indicators": [
            {"kind": k, **v} for k, v in CATALOG.items()
        ]}

    @api.get("/indicator/{kind}/{ticker:path}")
    def get_indicator(kind: str, ticker: str, period: int = 20,
                      interval: str = "1h", days: int = 30,
                      data_provider: str = "yfinance"):
        """
        An indicator series aligned to the same candles the chart draws.

        Computed here rather than in the browser so the overlay and the
        strategies read one implementation instead of two that drift.
        """
        from src.indicators import CATALOG, compute
        if kind not in CATALOG:
            raise HTTPException(400, f"unknown indicator: {kind}")

        bars = get_history(ticker, interval=interval, days=days,
                           data_provider=data_provider)["candles"]
        try:
            values = compute(kind, bars, period)
        except ValueError as e:
            raise HTTPException(400, str(e))

        return {
            "kind": kind,
            "label": CATALOG[kind]["label"],
            "pane": CATALOG[kind]["pane"],
            "period": period,
            # Gaps are dropped rather than sent as nulls: the chart wants a
            # series that starts where the data does.
            "points": [
                {"time": bars[i]["time"], "value": round(v, 6)}
                for i, v in enumerate(values) if v is not None
            ],
        }

    @api.post("/orders")
    def place_order(body: ManualOrderBody):
        """
        Place a single order by hand, outside any strategy.

        make_provider refuses to build a live provider, so this can only ever
        reach a paper account — placing a real-money order stays a deliberate,
        explicit act elsewhere.
        """
        if body.direction not in ("long", "short"):
            raise HTTPException(400, "direction must be 'long' or 'short'")
        if body.size <= 0:
            raise HTTPException(400, "size must be positive")

        provider = make_provider(body.provider, state.home)
        account_id = _resolve_account(provider, body.account_id, 10000.0)

        price = body.reference_price
        if price is None:
            from src.data_providers import make_data_provider
            prov = make_data_provider(body.data_provider, state.home)
            price, _ = prov.get_last_price(body.ticker)

        result = provider.execute_order(
            account_id=account_id, ticker=body.ticker, direction=body.direction,
            size=body.size, reference_price=price, timestamp=dt.datetime.now(),
            closing=body.closing,
        )
        fill = getattr(result, "fill_price", price)

        # A fill that leaves no record is invisible afterwards, which is why
        # placing an order used to look like nothing happened.
        from src.book import ManualBook
        pos = ManualBook(state.home).open(
            account_id=account_id, ticker=body.ticker, direction=body.direction,
            size=body.size, price=fill,
        )
        # Protective exits are placed against the new position, so closing it
        # by hand takes them with it.
        from src.orders import OrderBook
        book = OrderBook(state.home)
        closing_side = "short" if body.direction == "long" else "long"
        attached = []
        for kind, trigger in (("stop_loss", body.stop_loss),
                              ("take_profit", body.take_profit)):
            if trigger:
                attached.append(book.place(
                    account_id=account_id, ticker=body.ticker,
                    direction=closing_side, size=body.size,
                    order_type=kind, trigger_price=trigger,
                    position_id=pos["id"],
                ))

        return {
            "position_id": pos["id"],
            "attached_orders": [o["id"] for o in attached],
            "account_id": account_id,
            "ticker": body.ticker,
            "direction": body.direction,
            "size": body.size,
            "fill_price": fill,
            "balance": provider.get_account_balance(account_id),
        }

    # ---- pending orders ----

    @api.get("/orders/pending")
    def list_pending(account_id: Optional[str] = None, ticker: Optional[str] = None):
        from src.orders import ORDER_TYPES, OrderBook
        return {
            "orders": OrderBook(state.home).list(account_id, ticker),
            "types": [{"kind": k, "description": v} for k, v in ORDER_TYPES.items()],
        }

    @api.post("/orders/pending")
    def place_pending(body: PendingOrderBody):
        """
        Rest an order until the market reaches it.

        The execution provider fills the moment it is called, so anything
        conditional waits here and the monitor releases it.
        """
        from src.orders import OrderBook
        provider = make_provider("simulated", state.home)
        account_id = _resolve_account(provider, body.account_id, 10000.0)
        try:
            return OrderBook(state.home).place(
                account_id=account_id, ticker=body.ticker, direction=body.direction,
                size=body.size, order_type=body.order_type,
                trigger_price=body.trigger_price, limit_price=body.limit_price,
                position_id=body.position_id,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    @api.delete("/orders/pending/{order_id}")
    def cancel_pending(order_id: str):
        from src.orders import OrderBook
        try:
            return OrderBook(state.home).cancel(order_id)
        except KeyError:
            raise HTTPException(404, "unknown order")

    @api.post("/positions/{position_id}/close")
    def close_position(position_id: str, price: Optional[float] = None,
                       data_provider: str = "yfinance"):
        """Close a manual position at market, or at an explicit price."""
        from src.book import ManualBook
        book = ManualBook(state.home)
        pos = book.get(position_id)
        if not pos:
            raise HTTPException(404, "unknown position")

        if price is None:
            from src.data_providers import make_data_provider
            prov = make_data_provider(data_provider, state.home)
            price, _ = prov.get_last_price(pos["ticker"])

        provider = make_provider("simulated", state.home)
        provider.execute_order(
            account_id=pos["account_id"], ticker=pos["ticker"],
            direction="short" if pos["direction"] == "long" else "long",
            size=pos["size"], reference_price=price,
            timestamp=dt.datetime.now(), closing=True,
        )
        closed = book.close(position_id, price)
        provider.on_trade_closed(pos["account_id"], closed["pnl"])
        # A stop-loss left working after its position closed would open a new
        # position in the opposite direction the next time it triggered.
        from src.orders import OrderBook
        OrderBook(state.home).cancel_for_position(position_id)
        return closed

    @api.get("/positions/{position_id}")
    def get_position(position_id: str, data_provider: str = "yfinance"):
        """One position with its live mark, for inspection."""
        from src.book import ManualBook
        pos = ManualBook(state.home).get(position_id)
        if not pos:
            raise HTTPException(404, "unknown position")

        mark = unrealised = None
        try:
            from src.data_providers import make_data_provider
            prov = make_data_provider(data_provider, state.home)
            mark, _ = prov.get_last_price(pos["ticker"])
            sign = 1 if pos["direction"] == "long" else -1
            unrealised = round(sign * (mark - pos["entry_price"]) * pos["size"], 2)
        except Exception:
            pass  # a quote failure should not hide the position itself
        return {**pos, "mark": mark, "unrealised_pnl": unrealised}

    # ---- jobs ----

    @api.get("/jobs")
    def list_jobs():
        # Results can be large; the list view only needs metadata.
        return {"jobs": [j.to_dict(include_result=False) for j in state.jobs.list()]}

    @api.get("/jobs/{job_id}")
    def get_job(job_id: str):
        job = state.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "unknown job_id")
        return job.to_dict()

    @api.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        if not state.jobs.cancel(job_id):
            raise HTTPException(400, "job is unknown or already finished")
        return {"cancelling": job_id}

    @api.get("/rankings")
    def get_rankings():
        from src.agents.forker import load_all_rolling
        return {"rankings": [r.to_dict() for r in load_all_rolling(state.home)]}

    # ---- meta ----

    @api.get("/config")
    def get_config():
        from src import __version__
        from src.config import _DEFAULT_HOME, home_source
        from src.data_providers import DATA_PROVIDERS
        return {
            "version": __version__,
            "home": state.home,
            "home_source": home_source(),
            "default_home": _DEFAULT_HOME,
            "data_providers": sorted(DATA_PROVIDERS),
            "execution_providers": sorted(PROVIDERS),
        }

    @api.put("/config/home")
    def set_config_home(body: SetHomeBody):
        """
        Point the app at a different data directory from next start.

        The running process keeps its current home: swapping it live would
        leave open files and cached state pointing at the old location. An
        env var or --data-dir still wins, so say so rather than let the
        setting look ignored.
        """
        from src.config import SUBDIRS, home_source, set_home_preference

        target = pathlib.Path(body.home).expanduser()
        try:
            for sub in SUBDIRS:
                (target / sub).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise HTTPException(400, f"cannot use that directory: {e}")

        saved = set_home_preference(str(target))
        overridden = home_source() in ("--data-dir", "MONEYMAKER_HOME")
        return {
            "home": saved,
            "restart_required": True,
            "overridden_by": home_source() if overridden else None,
        }

    @api.get("/equity")
    def get_equity(limit: int = 500):
        """
        Cumulative P&L over time across every recorded session.

        Trades are pooled from all session logs and ordered by exit time, so
        the curve reads as one continuous account history rather than a set
        of disconnected runs.
        """
        sess_dir = pathlib.Path(state.home) / "sessions"
        trades: list[tuple[str, float]] = []
        if sess_dir.is_dir():
            for path in sess_dir.glob("*.csv"):
                try:
                    with open(path) as f:
                        for r in csv.DictReader(f):
                            raw, when = r.get("pnl"), (r.get("exit_time") or r.get("entry_time"))
                            if raw in (None, "") or not when:
                                continue
                            trades.append((when, float(raw)))
                except (OSError, ValueError):
                    continue

        trades.sort(key=lambda t: t[0])
        # Long histories are downsampled so the payload stays small; the
        # shape of the curve survives, which is all the chart needs.
        step = max(1, len(trades) // limit)
        points, running = [], 0.0
        for i, (when, pnl) in enumerate(trades):
            running += pnl
            if i % step == 0 or i == len(trades) - 1:
                points.append({"i": i + 1, "t": when[:19], "equity": round(running, 2)})
        return {"points": points, "trades": len(trades),
                "final": round(running, 2)}

    @api.get("/positions")
    def get_positions(account_id: Optional[str] = None, limit: int = 500):
        """
        Every trade this account has taken, open and closed.

        Trade logs carry the account they ran against, so the portfolio can
        be scoped to one account or shown whole. A row with no exit is still
        open.
        """
        sess_dir = pathlib.Path(state.home) / "sessions"
        open_rows: list[dict] = []
        closed_rows: list[dict] = []

        if sess_dir.is_dir():
            files = sorted(sess_dir.glob("*.csv"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            for path in files:
                try:
                    with open(path) as f:
                        rows = list(csv.DictReader(f))
                except OSError:
                    continue
                for r in rows:
                    if account_id and r.get("account_id") != account_id:
                        continue
                    entry = {
                        "run": path.stem,
                        "ticker": r.get("ticker") or "",
                        "direction": r.get("direction") or "",
                        "size": _num(r.get("size")),
                        "entry_time": r.get("entry_time") or "",
                        "entry_price": _num(r.get("entry_price")),
                        "exit_time": r.get("exit_time") or "",
                        "exit_price": _num(r.get("exit_price")),
                        "exit_reason": r.get("exit_reason") or "",
                        "pnl": _num(r.get("pnl")),
                        "pnl_pct": r.get("pnl_pct") or "",
                        "account_id": r.get("account_id") or "",
                    }
                    (closed_rows if r.get("exit_time") else open_rows).append(entry)

        # Manual positions live in their own book until closed, marked to
        # market so the view shows what they are worth now.
        marked, unrealised = _mark_open(state.home, account_id)
        for m in marked:
            open_rows.append({
                "run": "manual", "id": m["id"],
                "ticker": m["ticker"], "direction": m["direction"],
                "size": m["size"], "entry_time": m["entry_time"],
                "entry_price": m["entry_price"], "exit_time": "", "exit_price": None,
                "exit_reason": "", "pnl": None, "pnl_pct": "",
                "account_id": m["account_id"],
                "mark": m["mark"], "unrealised_pnl": m["unrealised_pnl"],
            })

        closed_rows.sort(key=lambda t: t["entry_time"], reverse=True)
        realised = round(sum(t["pnl"] or 0.0 for t in closed_rows), 2)
        return {
            "open": open_rows[:limit],
            "closed": closed_rows[:limit],
            "open_count": len(open_rows),
            "closed_count": len(closed_rows),
            "realised_pnl": realised,
            "unrealised_pnl": unrealised,
            "total_pnl": round(realised + unrealised, 2),
        }

    @api.get("/pnl-distribution")
    def get_pnl_distribution(buckets: int = 21):
        """
        How P&L is composed: the spread of individual trade outcomes, plus
        the split between winners and losers.

        A net figure hides whether it came from many small edges or one
        outlier, which is the difference between a system worth running and
        one that got lucky.
        """
        sess_dir = pathlib.Path(state.home) / "sessions"
        pnls: list[float] = []
        if sess_dir.is_dir():
            for path in sess_dir.glob("*.csv"):
                try:
                    with open(path) as f:
                        for r in csv.DictReader(f):
                            raw = r.get("pnl")
                            if raw not in (None, ""):
                                pnls.append(float(raw))
                except (OSError, ValueError):
                    continue

        if not pnls:
            return {"buckets": [], "wins": 0, "losses": 0,
                    "gross_win": 0.0, "gross_loss": 0.0, "trades": 0}

        lo, hi = min(pnls), max(pnls)
        if hi == lo:
            hi = lo + 1.0
        n = max(5, min(buckets, 51))
        width = (hi - lo) / n
        counts = [0] * n
        sums = [0.0] * n
        for v in pnls:
            i = min(int((v - lo) / width), n - 1)
            counts[i] += 1
            sums[i] += v

        wins = [v for v in pnls if v > 0]
        losses = [v for v in pnls if v < 0]
        return {
            "buckets": [
                {"lo": round(lo + i * width, 2),
                 "hi": round(lo + (i + 1) * width, 2),
                 "mid": round(lo + (i + 0.5) * width, 2),
                 "count": counts[i],
                 "pnl": round(sums[i], 2)}
                for i in range(n)
            ],
            "trades": len(pnls),
            "wins": len(wins),
            "losses": len(losses),
            "gross_win": round(sum(wins), 2),
            "gross_loss": round(sum(losses), 2),
        }

    @api.get("/stats")
    def get_stats():
        """
        Aggregate numbers for the dashboard, computed across every recorded
        session rather than just the live ones.
        """
        sess_dir = pathlib.Path(state.home) / "sessions"
        pnls: list[float] = []
        sessions = 0
        best = worst = None
        tickers: set[str] = set()

        if sess_dir.is_dir():
            for path in sess_dir.glob("*.csv"):
                sessions += 1
                try:
                    with open(path) as f:
                        rows = list(csv.DictReader(f))
                except OSError:
                    continue
                for r in rows:
                    if r.get("ticker"):
                        tickers.add(r["ticker"])
                    raw = r.get("pnl")
                    if raw in (None, ""):
                        continue
                    try:
                        pnls.append(float(raw))
                    except ValueError:
                        continue

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        if pnls:
            best, worst = max(pnls), min(pnls)

        mgr = AccountManager(state.home)
        accounts = mgr.list()
        open_rows, unrealised = _mark_open(state.home)
        realised = round(sum(pnls), 2)

        return {
            "sessions": sessions,
            "accounts": len(accounts),
            "total_balance": round(sum(a.balance for a in accounts), 2),
            "trades": len(pnls),
            "realised_pnl": realised,
            "unrealised_pnl": unrealised,
            "open_positions": len(open_rows),
            # total_pnl now means realised + unrealised, so an open trade is
            # visible in the headline rather than only after it closes.
            "total_pnl": round(realised + unrealised, 2),
            "win_rate": round(len(wins) / len(pnls), 4) if pnls else None,
            "wins": len(wins),
            "losses": len(losses),
            "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
            "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
            "best_trade": round(best, 2) if best is not None else None,
            "worst_trade": round(worst, 2) if worst is not None else None,
            "profit_factor": (round(sum(wins) / abs(sum(losses)), 2)
                              if losses and sum(losses) else None),
            "strategies": len(load_strategies(state.home)),
            "live_sessions": len(state.sessions),
        }

    # ---- live ----

    @api.get("/live/list")
    def list_live():
        with state.lock:
            return {"session_ids": list(state.sessions.keys())}

    @api.get("/live/{session_id}/status")
    def live_status(session_id: str):
        with state.lock:
            sim = state.sessions.get(session_id)
        if not sim:
            raise HTTPException(404, "unknown session_id")
        return _status_payload(sim)

    @api.post("/live/start")
    def live_start(body: LiveStartBody):
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")
        strategy = strategy_cls()
        provider = make_provider(body.provider, state.home)
        account_id = _resolve_account(provider, body.account_id, body.account)
        risk = RiskManager(risk_pct=body.risk_pct)
        sid = uuid.uuid4().hex[:12]
        logger = TradeLogger(state.home, f"live_{body.strategy}_{sid}")
        sim = Simulator(strategy, provider, account_id, risk, logger, ticker=body.ticker)
        end_time = dt.datetime.strptime(body.end_time, "%H:%M").time()

        def _run():
            sim.run_live(body.ticker, body.poll_seconds, end_time)

        th = threading.Thread(target=_run, daemon=True)
        with state.lock:
            state.sessions[sid] = sim
        th.start()
        return {"session_id": sid, "account_id": account_id}

    @api.post("/live/{session_id}/stop")
    def live_stop(session_id: str):
        with state.lock:
            sim = state.sessions.get(session_id)
        if not sim:
            raise HTTPException(404, "unknown session_id")
        sim.stopped.set()
        return {"stopped": session_id}

    # ---- resting-order monitor ----

    def _sweep_orders() -> None:
        """
        Fill any resting order the market has reached.

        Runs on a timer rather than a price stream because the free data
        providers are polled anyway — yfinance is ~15s delayed, so a tighter
        loop would only re-read the same quote.
        """
        from src.data_providers import make_data_provider
        from src.orders import OrderBook, fill_price_for

        book = OrderBook(state.home)
        prov = make_data_provider("yfinance", state.home)

        def quote(ticker: str) -> Optional[float]:
            return prov.get_last_price(ticker)[0]

        for order, market_price in book.marketable(quote):
            fill = fill_price_for(order, market_price)
            provider = make_provider("simulated", state.home)
            try:
                provider.execute_order(
                    account_id=order["account_id"], ticker=order["ticker"],
                    direction=order["direction"], size=order["size"],
                    reference_price=fill, timestamp=dt.datetime.now(),
                    closing=bool(order.get("position_id")),
                )
            except Exception as e:
                log.warning("order %s failed to fill: %s", order["id"], e)
                continue

            from src.book import ManualBook
            mbook = ManualBook(state.home)
            if order.get("position_id"):
                # A protective exit closes the position it guards.
                try:
                    closed = mbook.close(order["position_id"], fill,
                                         reason=order["type"])
                    provider.on_trade_closed(order["account_id"], closed["pnl"])
                except KeyError:
                    pass          # position already gone; drop the order
                book.cancel_for_position(order["position_id"])
            else:
                mbook.open(account_id=order["account_id"], ticker=order["ticker"],
                           direction=order["direction"], size=order["size"],
                           price=fill, note=f"{order['type']} order {order['id']}")
                book.remove(order["id"])

    def _monitor_loop() -> None:
        while not state.monitor_stop.wait(20):
            try:
                _sweep_orders()
                state.last_sweep = dt.datetime.now().isoformat(timespec="seconds")
                state.sweep_error = None
            except Exception as e:
                # The monitor must outlive a bad quote or a missing provider.
                state.sweep_error = f"{type(e).__name__}: {e}"
                log.exception("order sweep failed")

    threading.Thread(target=_monitor_loop, daemon=True).start()

    @api.get("/orders/monitor")
    def monitor_status():
        """Whether resting orders are actually being watched."""
        from src.orders import OrderBook
        return {
            "running": not state.monitor_stop.is_set(),
            "interval_seconds": 20,
            "last_sweep": state.last_sweep,
            "error": state.sweep_error,
            "working_orders": len(OrderBook(state.home).list()),
        }

    app.include_router(api)

    # Serve the built React SPA — only when ui/dist exists (production).
    dist = ui_dist or (pathlib.Path(__file__).parent.parent / "ui" / "dist")
    if dist.is_dir():
        # Real files (JS, CSS, favicon) are served from /static and friends.
        static_dir = dist / "static"
        if static_dir.is_dir():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        index = dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            """
            Client-side routing fallback.

            StaticFiles(html=True) serves index.html for "/" but 404s every
            other path, so loading or refreshing /strategies directly broke
            in production. The dev server does its own fallback, which is
            why this only showed up under `serve --prod`.

            Anything that looks like a real file still 404s properly rather
            than silently returning HTML — that turns a missing asset into a
            confusing parse error instead of an obvious 404.
            """
            # Unknown API routes must stay JSON 404s — an API client should
            # never receive the HTML shell in place of an error.
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(404, "not found")
            candidate = dist / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            if "." in pathlib.PurePath(full_path).name:
                raise HTTPException(404, "not found")
            return FileResponse(index)

    return app


def create_app() -> FastAPI:
    """Zero-arg ASGI factory, for `uvicorn --factory src.server:create_app --reload`.

    Resolves the data home the same way the CLI does, so MONEYMAKER_HOME is
    still honoured. Uvicorn's reloader needs an importable zero-arg entry
    point; make_app() takes an explicit home and cannot serve that role.
    """
    from src.config import get_home
    return make_app(get_home())


def run_server(home: str, host: str = "127.0.0.1", port: int = 8787,
               reload: bool = False) -> None:
    import uvicorn
    print(f"moneymaker API  http://{host}:{port}/api/  (data: {home})")
    if reload:
        # The reloader re-imports in a subprocess, so it needs an import
        # string rather than an already-constructed app object.
        os.environ["MONEYMAKER_HOME"] = home
        uvicorn.run("src.server:create_app", factory=True, host=host, port=port,
                    reload=True, reload_dirs=[str(pathlib.Path(__file__).parent)])
    else:
        uvicorn.run(make_app(home), host=host, port=port)
