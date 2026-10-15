"""
Shared rate-limiter singleton for AERIS CampusProof.

Routers import `limiter` from here so they do not need to import from
app.main (which would create a circular dependency).  The actual
Limiter instance is created in app.main and stored on app.state; this
module simply re-exports the same object so decorators can reference it
at import time.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Module-level singleton — app.main overwrites app.state.limiter with
# this same object after app creation, so both references are in sync.
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
