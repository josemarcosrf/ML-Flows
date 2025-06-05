import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import UUID

import click
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterDeploymentId,
    FlowRunFilterState,
    FlowRunFilterStateName,
)
from tabulate import tabulate

VALID_STATES = [
    "Cancelled",
    "Crashed",
    "Completed",
    "Failed",
    "Paused",
    "Pending",
    "Running",
]


def parse_deployment_name(deployment_name: str):
    if "/" not in deployment_name:
        raise ValueError(
            "Deployment name must be in the format 'flow_name/deployment_name'. "
            "Example: 'my_flow/my_deployment'"
        )

    # Split into flow name and deployment name
    # e.g. "my_flow/my_deployment" -> ("my_flow", "my_deployment")
    flow_name, deployment_name = deployment_name.split("/")

    return flow_name, deployment_name


async def fetch_deployments(deployment_name: str):
    """Fetch deployments by name."""
    print(f"🔍 Searching for deployment: {deployment_name}")
    async with get_client() as client:
        return [d for d in await client.read_deployments() if d.name == deployment_name]


async def fetch_flow_runs(
    deployment_id: UUID | None = None,
    deployment_name: str | None = None,
    last_n_runs: int = 200,
    last_n_hours: int = 5,
    status: str | None = None,
) -> list:
    """Fetch recent flow runs for a given deployment."""

    if not deployment_id and not deployment_name:
        raise ValueError("Either deployment_id or deployment_name must be provided.")
    if deployment_id and deployment_name:
        raise ValueError(
            "Only one of deployment_id or deployment_name should be provided."
        )
    if deployment_name:
        # Fetch deployments by name first to get the ID
        deployments = await fetch_deployments(deployment_name)
        if not deployments:
            print(f"No deployments found with name: {deployment_name}")
            return []

        deployment_id = deployments[0].id
        print(f"🚀 Found deployment '{deployment_name}' with ID: {deployment_id}")

    print(f"🎣 Fetching flow runs for deployment ID: {deployment_id}")
    # Get current time and compute cutoff time
    now = datetime.now(timezone.utc)
    if last_n_hours >= 1:
        print(
            f"⏳ Fetching {last_n_runs} flow runs from the last {last_n_hours} hours..."
        )
        cutoff = now - timedelta(hours=last_n_hours)
    else:
        print(f"⏳ Fetching {last_n_runs} flow runs from the last 24 hours...")
        cutoff = now - timedelta(days=1)

    async with get_client() as client:
        # Query flow runs using deployment and flow filters
        # Ensure deployment_id is not None for the filter
        filter_deployment_id = [deployment_id] if deployment_id is not None else []
        flow_runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                deployment_id=FlowRunFilterDeploymentId(any_=filter_deployment_id)
                if filter_deployment_id
                else None,
                state=FlowRunFilterState(name=FlowRunFilterStateName(any_=[status]))
                if status
                else None,
            ),
            limit=last_n_runs,
        )

    # Filter flow runs for this deployment and started in the last N hours
    recent_runs = [
        run for run in flow_runs if run.start_time and run.start_time > cutoff
    ]
    print(
        f"🏃‍➡️  Found {len(recent_runs)} [{status or 'ANY'}] flow runs "
        f"for deployment '{deployment_id}' in the last {last_n_hours} hours."
    )

    return recent_runs


def common_flow_run_options(func):
    """Decorator to aggregate common click options for flow run commands."""
    options = [
        click.argument("deployment_name", type=str),
        click.option("-s", "--status", type=click.Choice(VALID_STATES)),
        click.option(
            "-n",
            "--last-n-runs",
            default=200,
            show_default=True,
            type=int,
            help="How many recent flow runs to fetch.",
        ),
        click.option(
            "-h",
            "--last-n-hours",
            default=5,
            show_default=True,
            type=int,
            help="How many hours back to look for flow runs.",
        ),
    ]
    for option in reversed(options):
        func = option(func)
    return func


@click.group()
def cli():
    """CLI for Prefect flow operations."""
    pass


@cli.command("flow-runs-to-params")
@common_flow_run_options
@click.option(
    "-o",
    "--output-path",
    type=click.Path(writable=True),
    required=True,
    help="Path to save the results as a JSON file.",
)
def flow_to_params(deployment_name, output_path, last_n_runs, last_n_hours, status):
    """CLI to get recent flow runs and their parameters for a deployment."""

    _, deployment_name = parse_deployment_name(deployment_name)

    filtered_runs = asyncio.run(
        fetch_flow_runs(
            deployment_name=deployment_name,
            last_n_runs=last_n_runs,
            last_n_hours=last_n_hours,
            status=status,
        )
    )

    # Extract parameters from the flow runs
    print(f"📂 Extracting parameters from {len(filtered_runs)} recent runs...")
    results = []
    for run in filtered_runs:
        url = run.parameters["file_paths"][0]
        fname = unquote(Path(urlparse(url).path).name)
        metadata = (
            run.parameters.get("metadatas", [{}])[0]
            if isinstance(run.parameters.get("metadatas", []), list)
            else {}
        )
        results.append({"file_name": fname, "metadata": metadata})

    print(
        f"📊 Displaying parameters for the first 5 runs of deployment "
        f"'{deployment_name}':"
    )
    print(tabulate(results[:5], headers="keys", tablefmt="grid"))

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"✅ Results saved to {output_path}")


@cli.command("lsr")
@common_flow_run_options
def ls_runs(deployment_name, status, last_n_runs, last_n_hours):
    """Fetch flow runs by status for a given deployment."""
    _, deployment_name = parse_deployment_name(deployment_name)

    filtered_runs = asyncio.run(
        fetch_flow_runs(
            deployment_name=deployment_name,
            last_n_runs=last_n_runs,
            last_n_hours=last_n_hours,
            status=status,
        )
    )
    if not filtered_runs:
        print(f"No runs found with status: {status}")
        return

    # Convert runs to a more readable format
    runs_list = [
        {
            "id": run.id,
            "name": run.name,
            "status": run.state.name,
            "start_time": run.start_time.isoformat() if run.start_time else None,
            "end_time": run.end_time.isoformat() if run.end_time else None,
            # "parameters": pformat(run.parameters),
        }
        for run in filtered_runs
    ]

    print(f"Found {len(filtered_runs)} runs with status '{status}':")
    print(tabulate(runs_list, headers="keys", tablefmt="grid"))


@cli.command("retry-runs")
@common_flow_run_options
def retry_runs(deployment_name, status, last_n_runs, last_n_hours):
    """Retry flow runs for a deployment, prompting before each retry."""

    async def set_run_pending(run_id):
        from prefect.states import Pending

        async with get_client() as client:
            await client.set_flow_run_state(run_id, state=Pending())
            print(f"🔄 Set run {run_id} to Pending (manual retry)")

    _, deployment_name = parse_deployment_name(deployment_name)

    filtered_runs = asyncio.run(
        fetch_flow_runs(
            deployment_name=deployment_name,
            last_n_runs=last_n_runs,
            last_n_hours=last_n_hours,
            status=status,
        )
    )
    if not filtered_runs:
        print(f"👀 No runs found with status: {status}")
        return

    for run in filtered_runs:
        print(
            f"\nRun ID: {run.id}\n"
            f"Name: {run.name}\n"
            f"Status: {run.state.name}\n"
            f"Start: {run.start_time}\n"
            f"End: {run.end_time}\n"
        )
        retry = input("Retry this run? [y/N]: ").strip().lower()
        if retry == "y":
            asyncio.run(set_run_pending(run.id))
        else:
            print("🦘 Skipped.")


if __name__ == "__main__":
    cli()
