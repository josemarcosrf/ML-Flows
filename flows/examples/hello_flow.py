from prefect import flow


@flow(log_prints=True)
def hello():
    print("Hello from Prefect on Fargate!")


if __name__ == "__main__":
    hello()
