"""
MAOS Main Entry Point.

Command-line interface for the Multi-Agent Orchestration System.
"""

import argparse
import asyncio
import sys
from pathlib import Path

import structlog
import uvicorn
from dotenv import load_dotenv

from maos.api.server import create_app_from_config
from maos.config.loader import ConfigLoader


def configure_logging(debug: bool = False) -> None:
    """Configure structured logging."""
    log_level = "DEBUG" if debug else "INFO"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.processors._NAME_TO_LEVEL[log_level.lower()]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


async def run_server(
    config_path: str,
    host: str | None = None,
    port: int | None = None,
    debug: bool = False,
) -> None:
    """Run the MAOS server.

    Args:
        config_path: Path to configuration file
        host: Override host from config
        port: Override port from config
        debug: Enable debug mode
    """
    log = structlog.get_logger()

    # Load configuration
    log.info("loading_config", path=config_path)
    loader = ConfigLoader()
    config = loader.load(config_path)

    # Override host/port if provided
    if host:
        config.serving.api.host = host
    if port:
        config.serving.api.port = port

    # Create application
    log.info("creating_application")
    app = await create_app_from_config(config)

    # Run server
    log.info(
        "starting_server",
        host=config.serving.api.host,
        port=config.serving.api.port,
    )

    server_config = uvicorn.Config(
        app,
        host=config.serving.api.host,
        port=config.serving.api.port,
        log_level="debug" if debug else "info",
    )
    server = uvicorn.Server(server_config)
    await server.serve()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="maos",
        description="Multi-Agent Orchestration System",
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--host", "-H",
        type=str,
        default=None,
        help="Override server host",
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="Override server port",
    )

    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode",
    )

    parser.add_argument(
        "--env-file",
        type=str,
        default=".env",
        help="Path to .env file (default: .env)",
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and exit",
    )

    args = parser.parse_args()

    # Load environment variables
    env_path = Path(args.env_file)
    if env_path.exists():
        load_dotenv(env_path)

    # Configure logging
    configure_logging(args.debug)
    log = structlog.get_logger()

    # Validate mode
    if args.validate:
        log.info("validating_config", path=args.config)
        try:
            loader = ConfigLoader()
            config = loader.load(args.config)
            log.info(
                "config_valid",
                llms=len(config.llms),
                agents=len(config.agents),
                tools=len(config.tools),
            )
            print("Configuration is valid!")
            sys.exit(0)
        except Exception as e:
            log.error("validation_failed", error=str(e))
            print(f"Configuration validation failed: {e}")
            sys.exit(1)

    # Check config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        log.error("config_not_found", path=args.config)
        print(f"Configuration file not found: {args.config}")
        sys.exit(1)

    # Run server
    try:
        asyncio.run(run_server(
            config_path=args.config,
            host=args.host,
            port=args.port,
            debug=args.debug,
        ))
    except KeyboardInterrupt:
        log.info("shutdown_requested")
    except Exception as e:
        log.error("server_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
