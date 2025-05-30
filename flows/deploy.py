from enum import Enum
from pathlib import Path
from typing import Callable

from prefect import Flow

from flows import collect_public_flows
from flows.settings import settings
from flows.shrag.helpers import get_project_version


class PoolType(str, Enum):
    DOCKER = "docker"
    PROCESS = "process"


def get_shared_env():
    env = {
        "DOCLING_BASE_URL": settings.DOCLING_BASE_URL,
        "OLLAMA_BASE_URL": settings.OLLAMA_BASE_URL,
        "CHROMA_HOST": settings.CHROMA_HOST,
        "CHROMA_PORT": str(settings.CHROMA_PORT),
        "REDIS_HOST": settings.REDIS_HOST,
        "REDIS_PORT": str(settings.REDIS_PORT),
    }
    # Add the secrets
    # TODO: Pass the secrets in a better way than environment variables
    env.update(
        {
            "OPENAI_API_KEY": settings.OPENAI_API_KEY.get_secret_value()
            if settings.OPENAI_API_KEY
            else None,
            "AWS_ACCESS_KEY_ID": settings.AWS_ACCESS_KEY_ID.get_secret_value()
            if settings.AWS_ACCESS_KEY_ID
            else None,
            "AWS_SECRET_ACCESS_KEY": settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
            if settings.AWS_SECRET_ACCESS_KEY
            else None,
        }
    )

    return env


def unwrap_flow(flow: Flow) -> Callable:
    """Unwraps a flow to get the original function and its code file path

    Args:
        flow (Flow): Prefect flow object

    Returns:
        str: The code file path and the function name
    """
    # Unwrap the function to get to the original function
    original_fn = flow.fn
    while hasattr(original_fn, "__wrapped__"):
        original_fn = original_fn.__wrapped__

    return original_fn


def deploy_flow(
    flow_name: str,
    deployment_name: str,
    pool_type: str,
    work_pool_name: str,
    build: bool = False,
    flow_tags: list[str] | None = None,
):
    """Deploys one of the PUBLIC dataflows
    For more information on Flow deployments, see:
    https://docs.prefect.io/latest/guides/prefect-deploy/
    """
    # Gather all the flows withing the 'dataflows' package
    public_flows = collect_public_flows()

    try:
        PoolType(pool_type)
    except ValueError as ve:
        raise ValueError(
            f"Invalid pool type: {pool_type}. "
            f"Must be one of: {', '.join(p.value for p in PoolType)}."
        ) from ve

    # Fetch the flow from its name
    if flow := public_flows.get(flow_name):
        print(f"🔖 FLOW TAGS: {flow_tags}")
        if pool_type.lower() == PoolType.DOCKER:
            image_name = "jmrf/shrag-prefect"
            project_version = get_project_version()
            if build:
                print(f"🔨 Building docker image: '{image_name}:{project_version}")

            flow.deploy(
                name=deployment_name,
                image=f"{image_name}:{project_version}",
                work_pool_name=work_pool_name,
                job_variables={"env": get_shared_env()},
                tags=flow_tags,
                build=build,
            )
        elif pool_type.lower() == PoolType.PROCESS:
            # NOTE: Using Flow.from_source() packages what is specified as 'source'.
            # This means we need to include the entire repo root so any imports in the
            # flow file can be included in the deployment.
            # This approach works well for standalone scripts but is limited when the flow
            # depends on additional local modules
            repo_root = Path.cwd()

            # NOTE: As the original function might be wrapper before wrapping it in a flow,
            # we need to unwrap it to get the original function code file path.
            fn = unwrap_flow(flow)
            flow_fn_name = fn.__name__
            code_file_path = Path(fn.__code__.co_filename)
            print(f"📦 Deploying flow: {flow_name} from {code_file_path}")

            Flow.from_source(
                source=str(repo_root),
                entrypoint=f"{code_file_path.relative_to(repo_root)}:{flow_fn_name}",
            ).deploy(  # type: ignore[attr-defined]
                name=deployment_name,
                work_pool_name=work_pool_name,
                job_variables={"env": get_shared_env()},
                tags=flow_tags,
            )
        else:
            raise NotImplementedError(
                f"Deployment for pool type {pool_type} not implemented yet"
            )
    else:
        print(f"💣 Couldn't find flow '{flow_name}'. Known flows are: {public_flows}")
