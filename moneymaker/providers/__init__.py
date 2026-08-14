from moneymaker.providers.base import ExecutionProvider, OrderResult
from moneymaker.providers.simulated import SimulatedExecutionProvider
from moneymaker.providers.trading212 import Trading212DemoProvider
from moneymaker.providers.ibkr import IBKRPaperProvider
from moneymaker.providers.oanda import OANDAPracticeProvider

PROVIDERS: dict[str, type[ExecutionProvider]] = {
    SimulatedExecutionProvider.name: SimulatedExecutionProvider,
    Trading212DemoProvider.name: Trading212DemoProvider,
    IBKRPaperProvider.name: IBKRPaperProvider,
    OANDAPracticeProvider.name: OANDAPracticeProvider,
}


def make_provider(name: str, home: str, credentials=None) -> ExecutionProvider:
    """
    Construct a provider by name. Refuses to construct anything marked
    is_live=True — wiring up a live, real-money provider must be done
    explicitly outside this helper, never as a side effect of a name string.
    """
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown provider '{name}'. Options: {list(PROVIDERS)}")
    if getattr(cls, "is_live", False):
        raise RuntimeError(
            f"Provider '{name}' is marked is_live=True — refusing to auto-construct it. "
            "Live providers must be wired up explicitly, outside this helper."
        )
    return cls(home, credentials=credentials)
