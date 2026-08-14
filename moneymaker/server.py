"""Local HTTP+JSON API server (stdlib only, no extra deps). Point a web UI,
TUI, or curl at it. Runs live sessions as background threads."""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from moneymaker.accounts import AccountManager, CredentialStore
from moneymaker.data import DataFeed
from moneymaker.engine import Simulator
from moneymaker.logger import TradeLogger
from moneymaker.providers import PROVIDERS, make_provider
from moneymaker.providers.simulated import SimulatedExecutionProvider
from moneymaker.risk import RiskManager
from moneymaker.strategy import BUILTIN_STRATEGIES, load_strategies


class ServerState:
    def __init__(self, home: str):
        self.home = home
        self.sessions: dict[str, Simulator] = {}
        self.lock = threading.Lock()


def make_handler(state: ServerState):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: dict):
            body = json.dumps(payload, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length))

        def log_message(self, fmt, *a):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]

            if parts == ["strategies"]:
                strategies = load_strategies(state.home)
                out = [{"name": n, "doc": (c.__doc__ or "").strip().split("\n")[0],
                        "source": "built-in" if n in BUILTIN_STRATEGIES else "custom"}
                       for n, c in strategies.items()]
                return self._json(200, {"strategies": out})

            if parts == ["providers"]:
                out = [{"name": n, "doc": (c.__doc__ or "").strip().split("\n")[0],
                        "status": "ready" if c is SimulatedExecutionProvider else "stub"}
                       for n, c in PROVIDERS.items()]
                return self._json(200, {"providers": out})

            if parts == ["accounts"]:
                mgr = AccountManager(state.home)
                return self._json(200, {"accounts": [a.to_dict() for a in mgr.list()]})

            if len(parts) == 2 and parts[0] == "accounts":
                mgr = AccountManager(state.home)
                info = mgr.get(parts[1])
                if not info:
                    return self._json(404, {"error": "not found"})
                return self._json(200, info.to_dict())

            if parts == ["credentials"]:
                store = CredentialStore(state.home)
                return self._json(200, {"credentials": store.list_masked()})

            if parts == ["sessions"]:
                sess_dir = os.path.join(state.home, "sessions")
                files = sorted(os.listdir(sess_dir)) if os.path.isdir(sess_dir) else []
                return self._json(200, {"sessions": files})

            if len(parts) == 2 and parts[0] == "sessions":
                path = os.path.join(state.home, "sessions", parts[1])
                if not os.path.exists(path):
                    return self._json(404, {"error": "not found"})
                with open(path) as f:
                    rows = list(csv.DictReader(f))
                return self._json(200, {"trades": rows})

            if len(parts) == 2 and parts[0] == "live" and parts[1] == "list":
                with state.lock:
                    return self._json(200, {"session_ids": list(state.sessions.keys())})

            if len(parts) == 3 and parts[0] == "live" and parts[2] == "status":
                sid = parts[1]
                with state.lock:
                    sim = state.sessions.get(sid)
                if not sim:
                    return self._json(404, {"error": "unknown session_id"})
                return self._json(200, sim.status())

            return self._json(404, {"error": "not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            body = self._read_json_body()

            if parts == ["accounts"]:
                try:
                    mgr = AccountManager(state.home)
                    a = mgr.create(
                        body["name"], body.get("provider", "simulated"),
                        currency=body.get("currency", "USD"),
                        starting_balance=body.get("starting_balance", 10000.0),
                        is_live=body.get("is_live", False),
                    )
                    return self._json(200, a.to_dict())
                except Exception as e:
                    return self._json(400, {"error": str(e)})

            if parts == ["credentials"]:
                try:
                    store = CredentialStore(state.home)
                    if body.get("env_var"):
                        store.set_ref(body["provider"], body["key"], body["env_var"])
                    elif body.get("value"):
                        store.set_value(body["provider"], body["key"], body["value"])
                    else:
                        return self._json(400, {"error": "provide env_var (recommended) or value"})
                    return self._json(200, {"ok": True})
                except Exception as e:
                    return self._json(400, {"error": str(e)})

            if parts == ["backtest"]:
                try:
                    strategies = load_strategies(state.home)
                    strategy_cls = strategies.get(body["strategy"])
                    if not strategy_cls:
                        return self._json(400, {"error": f"unknown strategy {body.get('strategy')}"})
                    feed = DataFeed(state.home)
                    df = feed.get_historical(
                        body["ticker"], body["start"], body["end"],
                        interval=body.get("interval", "5m"),
                    )
                    strategy = strategy_cls()
                    provider = make_provider(body.get("provider", "simulated"), state.home)
                    account_id = body.get("account_id")
                    if not account_id:
                        accts = provider.list_accounts()
                        account_id = accts[0].account_id if accts else provider.create_account(
                            "default", starting_balance=body.get("account", 10000.0)).account_id
                    risk = RiskManager(risk_pct=body.get("risk_pct", 0.01))
                    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                    logger = TradeLogger(state.home, f"backtest_{body['strategy']}_{ts}")
                    sim = Simulator(strategy, provider, account_id, risk, logger, ticker=body["ticker"])
                    sim.run_backtest(df)
                    return self._json(200, {"session_name": logger.session_name,
                                             "account_id": account_id, **sim.status()})
                except Exception as e:
                    return self._json(400, {"error": str(e)})

            if parts == ["live", "start"]:
                try:
                    strategies = load_strategies(state.home)
                    strategy_cls = strategies.get(body["strategy"])
                    if not strategy_cls:
                        return self._json(400, {"error": f"unknown strategy {body.get('strategy')}"})
                    strategy = strategy_cls()
                    provider = make_provider(body.get("provider", "simulated"), state.home)
                    account_id = body.get("account_id")
                    if not account_id:
                        accts = provider.list_accounts()
                        account_id = accts[0].account_id if accts else provider.create_account(
                            "default", starting_balance=body.get("account", 10000.0)).account_id
                    risk = RiskManager(risk_pct=body.get("risk_pct", 0.01))
                    sid = uuid.uuid4().hex[:12]
                    logger = TradeLogger(state.home, f"live_{body['strategy']}_{sid}")
                    sim = Simulator(strategy, provider, account_id, risk, logger, ticker=body["ticker"])
                    end_time = dt.datetime.strptime(body.get("end_time", "11:00"), "%H:%M").time()
                    poll_seconds = body.get("poll_seconds", 30)

                    def _run():
                        sim.run_live(body["ticker"], poll_seconds, end_time)

                    th = threading.Thread(target=_run, daemon=True)
                    with state.lock:
                        state.sessions[sid] = sim
                    th.start()
                    return self._json(200, {"session_id": sid, "account_id": account_id})
                except Exception as e:
                    return self._json(400, {"error": str(e)})

            if len(parts) == 3 and parts[0] == "live" and parts[2] == "stop":
                sid = parts[1]
                with state.lock:
                    sim = state.sessions.get(sid)
                if not sim:
                    return self._json(404, {"error": "unknown session_id"})
                sim.stopped.set()
                return self._json(200, {"stopped": sid})

            return self._json(404, {"error": "not found"})

    return Handler


def run_server(home: str, host: str = "127.0.0.1", port: int = 8787) -> None:
    state = ServerState(home)
    handler = make_handler(state)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"moneymaker API server on http://{host}:{port}  (data dir: {home})")
    print("Endpoints:")
    print("  GET  /strategies")
    print("  GET  /providers")
    print("  GET  /accounts               POST /accounts  {name, provider?, currency?, starting_balance?, is_live?}")
    print("  GET  /accounts/<id>")
    print("  GET  /credentials            POST /credentials  {provider, key, env_var?|value?}")
    print("  POST /backtest        {strategy, ticker, start, end, interval?, provider?, account_id?, account?, risk_pct?}")
    print("  POST /live/start      {strategy, ticker, provider?, account_id?, account?, risk_pct?, end_time?, poll_seconds?}")
    print("  GET  /live/<id>/status        POST /live/<id>/stop")
    print("  GET  /live/list")
    print("  GET  /sessions                GET /sessions/<filename>")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.shutdown()
