from prefect import flow, get_run_logger


@flow(log_prints=True)
def hello():
    print("Hello from Prefect on Fargate!")
    logger = get_run_logger()
    logger.info("Hello from ECS!!")


if __name__ == "__main__":
    hello()
