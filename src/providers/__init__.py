import inspect

from src.providers.base import ExecutionProvider, OrderResult
from src.providers.simulated import SimulatedExecutionProvider
from src.providers.trading212 import Trading212DemoProvider
from src.providers.ibkr import IBKRPaperProvider
from src.providers.oanda import OANDAPracticeProvider

PROVIDERS: dict[str, type[ExecutionProvider]] = {
    SimulatedExecutionProvider.name: SimulatedExecutionProvider,
    Trading212DemoProvider.name: Trading212DemoProvider,
    IBKRPaperProvider.name: IBKRPaperProvider,
    OANDAPracticeProvider.name: OANDAPracticeProvider,
}


def make_provider(name: str, home: str, credentials=None,
                  ephemeral: bool = False) -> ExecutionProvider:
    """
    Construct a provider by name. Refuses to construct anything marked
    is_live=True — wiring up a live, real-money provider must be done
    explicitly outside this helper, never as a side effect of a name string.

    ephemeral=True asks the provider to keep its accounts in memory instead
    of writing them to accounts.json. Use it for throwaway backtest runs
    (multi-window, grid search, fork-eval) whose accounts are scratch space,
    not something the user ever wants to see. Providers that do not support
    it simply ignore it.
    """
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown provider '{name}'. Options: {list(PROVIDERS)}")
    if getattr(cls, "is_live", False):
        raise RuntimeError(
            f"Provider '{name}' is marked is_live=True — refusing to auto-construct it. "
            "Live providers must be wired up explicitly, outside this helper."
        )
    if ephemeral and "ephemeral" in inspect.signature(cls.__init__).parameters:
        return cls(home, credentials=credentials, ephemeral=True)
    return cls(home, credentials=credentials)
