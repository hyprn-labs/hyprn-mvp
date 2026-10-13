"""Per-owner API routers. Each module exposes ``router(deps) -> APIRouter`` holding one domain
owner's routes in registration order; ``api.create_app`` alone includes them, in the order that
fixes the generated contract's path order. A route module reaches only the edge helpers,
``contracts`` and the owner modules whose public functions it calls."""
