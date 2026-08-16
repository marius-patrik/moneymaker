"""FastAPI server. API lives under /api. Serves the built React SPA from ui/dist/ when present."""

from __future__ import annotations

import csv
import datetime as dt
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
        from src.data_providers import DATA_PROVIDERS
        return {
            "version": __version__,
            "home": state.home,
            "data_providers": sorted(DATA_PROVIDERS),
            "execution_providers": sorted(PROVIDERS),
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
