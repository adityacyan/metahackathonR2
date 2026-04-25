# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the API Lifecycle Migration Environment.

This module creates an HTTP server that exposes the MigrationEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

The API Lifecycle Migration environment trains RL agents on API evolution
scenarios, where agents must evolve v1 OpenAPI schemas while preserving
backward compatibility, managing breaking changes, and satisfying progressive
migration tickets.

Endpoints:
    - POST /reset: Reset the environment with new baseline schema and ticket queue
    - POST /step: Execute a migration action (submit evolved OpenAPI schema)
    - GET /state: Get current environment state with migration history
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.migration_app:app --reload --host 0.0.0.0 --port 8001

    # Production:
    uvicorn server.migration_app:app --host 0.0.0.0 --port 8001 --workers 4

    # Or run directly:
    python -m server.migration_app
"""
import sys
import os
import uvicorn
import argparse

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError("uv sync") from e

d = os.path.dirname(os.path.abspath(__file__))
p = os.path.dirname(d)
if p not in sys.path:
    sys.path.insert(0, p)

try:
    from migration_models import MigrationAction, MigrationObservation
    from server.migration_environment import MigrationEnvironment
except ImportError:
    from api_conformance_gym.migration_models import MigrationAction, MigrationObservation
    from api_conformance_gym.server.migration_environment import MigrationEnvironment

app = create_app(
    MigrationEnvironment,
    MigrationAction,
    MigrationObservation,
    env_name="api_lifecycle_migration",
    max_concurrent_envs=10,
)

def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--host", default="0.0.0.0")
    arg.add_argument("--port", type=int, default=8001)
    a = arg.parse_args()
    uvicorn.run(app, host=a.host, port=a.port)

if __name__ == "__main__":
    main()
