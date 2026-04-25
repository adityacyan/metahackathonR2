"""
FastAPI application for the API Lifecycle Migration Environment.
"""
import sys
import os
import uvicorn
import argparse
from fastapi import Response

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import dependencies
from openenv.core.env_server.http_server import create_app
from migration_models import MigrationAction, MigrationObservation
from server.migration_environment import MigrationEnvironment

# Create the FastAPI app
app = create_app(
    MigrationEnvironment,
    MigrationAction,
    MigrationObservation,
    env_name="api_lifecycle_migration",
    max_concurrent_envs=10,
)


@app.get("/")
def root() -> dict:
    """Simple root endpoint so browser hits do not return 404."""
    return {
        "service": "api_lifecycle_migration",
        "status": "ok",
        "docs": "/docs",
        "ws": "/ws",
    }


@app.get("/favicon.ico")
def favicon() -> Response:
    """Return empty favicon response to avoid 404 noise in logs."""
    return Response(status_code=204)


def main():
    """Run the server directly."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
