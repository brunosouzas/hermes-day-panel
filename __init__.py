"""hermes-day-panel: a Today page in Hermes Desktop built from pluggable, read-only sources."""

from __future__ import annotations


def register(ctx) -> None:
    from .dp_cli import make_handler, setup_parser
    from .dp_host import path_from_ctx, shared_panel

    ctx.register_cli_command(
        name="day", help="Today page: show the sections, check the sources file", setup_fn=setup_parser,
        handler_fn=make_handler(lambda: path_from_ctx(ctx), shared_panel),
        description="Read the Today page's sections now (show) or validate the sources file (check).")
