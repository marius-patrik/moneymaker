"""FastAPI server. API lives under /api. Serves the built React SPA from ui/dist/ when present."""

from __future__ import annotations

import csv
import datetime as dt
import os
import pathlib
import threading
import uuid
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.accounts import AccountManager, CredentialStore
from src.data import DataFeed
from src.engine import Simulator
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

def make_app(home: str) -> FastAPI:
    state = ServerState(home)
    app = FastAPI(title="moneymaker", version="0.4.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        strategies = load_strategies(state.home)
        return {"strategies": [
            {"name": n, "doc": (c.__doc__ or "").strip().split("\n")[0],
             "source": "built-in" if n in BUILTIN_STRATEGIES else "custom",
             "params": {k: _jsonable(v) for k, v in c.params().items()} if hasattr(c, "params") else {}}
            for n, c in strategies.items()
        ]}

    # ---- providers ----

    @api.get("/providers")
    def list_providers():
        return {"providers": [
            {"name": n, "doc": (c.__doc__ or "").strip().split("\n")[0],
             "status": "ready" if c is SimulatedExecutionProvider else "stub"}
            for n, c in PROVIDERS.items()
        ]}

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

    # ---- sessions ----

    @api.get("/sessions")
    def list_sessions():
        sess_dir = os.path.join(state.home, "sessions")
        files = sorted(os.listdir(sess_dir)) if os.path.isdir(sess_dir) else []
        return {"sessions": files}

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
        feed = DataFeed(state.home)
        df = feed.get_historical(body.ticker, body.start, body.end, interval=body.interval)
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
    def run_optimize(body: OptimizeBody):
        strategies = load_strategies(state.home)
        strategy_cls = strategies.get(body.strategy)
        if not strategy_cls:
            raise HTTPException(400, f"unknown strategy: {body.strategy}")
        train_windows = [tuple(w) for w in body.train_windows]
        test_windows = [tuple(w) for w in body.test_windows] if body.test_windows else None
        result = grid_search(
            strategy_cls=strategy_cls, param_grid=body.param_grid,
            provider_name=body.provider, home=state.home,
            ticker=body.ticker, train_windows=train_windows, test_windows=test_windows,
            interval=body.interval, account_balance=body.account, risk_pct=body.risk_pct,
        )
        return result.to_dict(default_objective)

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

    app.include_router(api)

    # Serve built React SPA — only if ui/dist exists (production)
    dist = pathlib.Path(__file__).parent.parent / "ui" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")

    return app


def run_server(home: str, host: str = "127.0.0.1", port: int = 8787) -> None:
    import uvicorn
    app = make_app(home)
    print(f"moneymaker API  http://{host}:{port}/api/  (data: {home})")
    uvicorn.run(app, host=host, port=port)
