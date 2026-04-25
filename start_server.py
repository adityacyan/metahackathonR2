#!/usr/bin/env python3
"""Start the API Lifecycle Migration environment server."""

import os
import sys
import uvicorn

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def main():
    port = int(os.getenv("PORT", 7860))
    print(f"Starting API Lifecycle Migration server on port {port}...")
    print(f"API docs: http://localhost:{port}/docs")
    os.chdir(current_dir)
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

if __name__ == "__main__":
    main()
