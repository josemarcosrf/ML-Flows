from enum import Enum
from pathlib import Path

from prefect import Flow

from flows import collect_public_flows
from flows.shrag.constants import OPENAI_API_KEY_ENV_VAR
from flows.shrag.helpers import get_or_raise, get_project_version


class PoolType(str, Enum):
    DOCKER = "docker"
    PROCESS = "process"


# Environment variables shared with Prefect. Different flows will have different needs
# aws_key, aws_secret = get_aws_credentials()


def get_shared_env():
    # Wrapped in a function to avoid 'get_or_raise' on import, only @ run-time
    return {
        "OPENAI_API_KEY": get_or_raise(OPENAI_API_KEY_ENV_VAR),
        # "RAY_ADDRESS": get_or_raise("RAY_ADDRESS"),
        # "AWS_ACCESS_KEY_ID": aws_key,
        # "AWS_SECRET_ACCESS_KEY": aws_secret,
    }


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
        print("🔖 FLOW TAGS: ", flow_tags)
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
            flow_fn_name = flow.fn.__name__
            repo_root = Path.cwd()
            code_file_path = Path(flow.fn.__code__.co_filename)
            Flow.from_source(
                source=str(repo_root),
                entrypoint=f"{code_file_path.relative_to(repo_root)}:{flow_fn_name}",
            ).deploy(  # type: ignore[attr-defined]
                name=deployment_name,
                work_pool_name=work_pool_name,
                tags=flow_tags,
            )
        else:
            raise NotImplementedError(
                f"Deployment for pool type {pool_type} not implemented yet"
            )
    else:
        print(f"💣 Couldn't find flow '{flow_name}'. Known flows are: {public_flows}")
