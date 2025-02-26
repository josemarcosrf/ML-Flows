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
def start_worker_pool(
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

    c.run(
        f"prefect work-pool create --type {pool_type} {name} "
        f"{'--overwrite' if overwrite else ''} &"
    )
    c.run("prefect work-pool ls")
    c.run(f"prefect worker start --pool {name}")
