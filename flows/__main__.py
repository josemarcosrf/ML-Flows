import base64
import json
import os
import uuid
from pathlib import Path

import click
import cloudpickle
from tabulate import tabulate

from flows import collect_public_flows
from flows.cli.chroma import chroma_cli
from flows.cli.pubsub import pubsub_cli
from flows.deploy import deploy_flow, PoolType, unwrap_flow
from flows.preproc.__main__ import preproc_cli
from flows.settings import print_settings, settings
from flows.shrag.__main__ import shrag_cli


@click.group()
def cli():
    """Flows CLI"""


@cli.command("settings")
def print_settings_cli():
    """Print settings"""
    print_settings(settings)


@cli.command("ls")
def list_flows():
    """List all publicly available flows"""
    repo_root = Path.cwd()
    rows = []
    headers = ["Flow Name", "From", "Flow Parameters"]
    for flow_name, flow in collect_public_flows().items():
        code_file_path = Path(unwrap_flow(flow).__code__.co_filename)
        flow_path = code_file_path.relative_to(repo_root)
        flow_params = {
            p: p_info.get("description", "N/D")
            for p, p_info in flow.parameters.properties.items()
        }
        params_str = "- " + "\n- ".join(f"{p}: {d}" for p, d in flow_params.items())
        rows.append((flow_name, flow_path, params_str))
    print(
        tabulate(
            rows,
            headers,
            tablefmt="fancy_grid",
            showindex=True,
        )
    )


@cli.command("deploy")
@click.argument("flow_name", type=click.Choice(list(collect_public_flows().keys())))
@click.argument("deployment_name")
@click.argument("pool-type", type=click.Choice([p.value for p in PoolType]))
@click.argument("work-pool-name")
@click.option("-b", "--build", is_flag=True)
@click.option("-t", "--flow_tags", multiple=True, default=["DEUS"])
def deploy_flow_cli(
    flow_name: str,
    deployment_name: str,
    pool_type: str,
    work_pool_name: str,
    build: bool = False,
    flow_tags: list[str] | None = None,
):
    """Deploy a public flow to a Docker or Process pool.

    e.g.: Deploy the playbook-qa flow to a deployment called DEV on a 'Process' pool named 'test'
    python -m flows deploy playbook-qa DEV process test -t qa -t playbook

    Args:
        flow_name (str): Name fo the flow to deploy
        deployment_name (str): Name under which the flow will be deployed
        pool_type (str): Prefect type of pool to deploy to
        work_pool_name (str): Name of the Prefect work pool
        build (bool, optional): Wether to build docker image. Defaults to False.
        flow_tags (list[str] | None, optional): List of Prefect tags. Defaults to ['DEUS'].
    """
    deploy_flow(flow_name, deployment_name, pool_type, work_pool_name, build, flow_tags)


@cli.command("read-result")
@click.option("--run-id")
@click.option("--result-id")
@click.option(
    "-s",
    "--storage-path",
    default=settings.PREFECT_STORAGE_PATH,
)
def read_prefect_result(
    run_id: str | None, result_id: str | None = None, storage_path: str | None = None
):
    """Read a result from the Prefect storage

    Args:
        run_id (str): The ID of the flow or task that produced the result
        result_id (str): The ID of the result to read
        storage_path (str): The path where Prefect stores the results
    """
    storage_path = storage_path or os.getenv("PREFECT_STORAGE_PATH")
    if not storage_path:
        print("💥 Please provide a storage path")
        return

    if not run_id and not result_id:
        print("💥 Please provide a run ID OR a result ID")
        return

    if run_id:
        print("🎰 Computing result ID from run ID...")
        result_id = (
            base64.urlsafe_b64encode(uuid.UUID(run_id).bytes).decode().rstrip("=")
        )

    rfile = Path(storage_path).resolve() / result_id
    if rfile.exists():
        try:
            res = json.load(rfile.open("rb"))
            res = cloudpickle.loads(base64.b64decode(res["result"]))
        except json.JSONDecodeError:
            print(f"💥 {rfile} is not a valid JSON file!")
            return

        print(json.dumps(res, indent=2))
    else:
        print(f"💥 {rfile} could not be found!")


def main():
    cli.add_command(chroma_cli)
    cli.add_command(pubsub_cli)
    cli.add_command(preproc_cli)
    cli.add_command(shrag_cli)
    cli()


if __name__ == "__main__":
    main()
