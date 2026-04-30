import yaml


def save_conn_params(params, filename="params.yaml"):
    with open(filename, "w") as f:
        yaml.safe_dump(params, f)


def load_conn_params(filename="params.yaml"):
    try:
        with open(filename, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
