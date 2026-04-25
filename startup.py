#!/usr/bin/env python3
"""
Startup script for HuggingFace Spaces deployment.
Provides better error handling and debugging information.
"""
import sys
import os
import traceback
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main startup function with error handling."""
    try:
        logger.info("Starting API Lifecycle Migration Environment...")
        
        # Add current directory to Python path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
        
        logger.info(f"Python path: {sys.path[:3]}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Test imports
        logger.info("Testing imports...")
        
        try:
            from openenv.core.env_server.http_server import create_app
            logger.info("✓ openenv imported successfully")
        except ImportError as e:
            logger.error(f"✗ Failed to import openenv: {e}")
            raise
        
        try:
            from migration_models import MigrationAction, MigrationObservation
            logger.info("✓ migration_models imported successfully")
        except ImportError as e:
            logger.error(f"✗ Failed to import migration_models: {e}")
            raise
        
        try:
            from server.migration_environment import MigrationEnvironment
            logger.info("✓ MigrationEnvironment imported successfully")
        except ImportError as e:
            logger.error(f"✗ Failed to import MigrationEnvironment: {e}")
            raise
        
        # Create app
        logger.info("Creating FastAPI app...")
        app = create_app(
            MigrationEnvironment,
            MigrationAction,
            MigrationObservation,
            env_name="api_lifecycle_migration",
            max_concurrent_envs=10,
        )
        logger.info("✓ FastAPI app created successfully")
        
        # Start server
        import uvicorn
        port = int(os.getenv("PORT", 7860))
        host = os.getenv("HOST", "0.0.0.0")
        
        logger.info(f"Starting server on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="info")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()