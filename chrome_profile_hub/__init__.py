"""Chrome Profile Hub - one table for all your logged-in Chrome profiles, shared by humans and AI agents."""
__version__ = "0.1.0"
from .core import catalog, find, start, open_chrome, agent_page, new_profile, open_url, close_profile, port_open  # noqa: F401
from .scanner import scan, pick, set_meta, SERVICES  # noqa: F401
