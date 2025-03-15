import os
import re
from enum import Enum

from invoke import task


@task
def local_chroma(c, port: int = 8000):
    """Start a local ChromaDB server (port 8000 by default)

    Args:
        port (int): Port to run the ChromaDB server on. Defaults to 8000.
    """
    c.run(f"chroma run --port {port}")


@task
def local_prefect(c, port: int = 4200):
    """Start a local Prefect server (port 4200 by default)"""
    c.run("prefect server start")
    c.run(f"prefect config set PREFECT_API_URL=http://127.0.0.1:{port}/api")


@task
def local_worker_pool(
    c, pool_type: str, name: str | None = None, overwrite: bool = False
) -> None:
    """Creates and starts a Docker Worker Pool

    Args:
        pool_type (str): Prefect Work Pool type (process OR docker)
    """

    class PoolType(str, Enum):
        """Pool types for Prefect Work Pools"""

        DOCKER = "docker"
        PROCESS = "process"

    try:
        # Validate the pool-type parameter
        _ = PoolType(pool_type)
    except ValueError as ve:
        raise ValueError(
            f"Invalid pool type: {pool_type}. "
            f"Must be one of: {', '.join(p.value for p in PoolType)}."
        ) from ve

    if name is None:
        name = f"local-{pool_type}-pool"
        print(f"🎱 Using default pool name: {name}")

    c.run(
        f"prefect work-pool create --type {pool_type} {name} "
        f"{'--overwrite' if overwrite else ''} &"
    )
    c.run("prefect work-pool ls")
    c.run(f"prefect worker start --pool {name}")


@task
def local_marker_ocr(c):
    """Start a local Marker-PDF Converter served by Ray (port 8001 by default)"""
    c.run(".venv/bin/serve run -r services.ocr:converter")


@task
def local_ray(ctx, port: int | None = None, n_nodes: int = 1):
    """Start a local Ray server (port 6789 by default)"""

    # Start Ray on the given port
    port = port or os.getenv("RAY_HEAD_PORT", 6789)
    result = ctx.run(
        f"ray stop && ray start --head --port={port}", hide=False, warn=True
    )
    # Find the Ray address
    # NOTE: Theoretically getting the IP could be done with: `ray get-head-ip`
    #       But in practice is not working without a config file
    address_regex = r"--address=\'([^\']+)\'"
    if m := re.search(address_regex, result.stdout):
        addr = m.group(1)

        # Start as many nodes as requested
        for _ in range(n_nodes - 1):
            ctx.run(f"ray start --address={addr}", hide=False, warn=True)

        # Update the .env file
        if (
            input("Do you want to update the 'RAY_ADDRESS' in the .env file? ").lower()
            == "y"
        ):
            print("🖊  Updating .env file ")
            ctx.run(f'sed -i "s/RAY_ADDRESS=.*/RAY_ADDRESS=\\"{addr}\\"/" .env')
