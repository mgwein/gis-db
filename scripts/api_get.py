import argparse
import json
import warnings


def main():
    warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")
    from fastapi.testclient import TestClient

    from gisdb.api.app import app

    parser = argparse.ArgumentParser(
        prog="api_get", usage="api_get [--request-id ID] PATH [PATH ...]"
    )
    parser.add_argument("--request-id")
    parser.add_argument("paths", nargs="+", metavar="PATH")

    args = parser.parse_args()

    client = TestClient(app)

    for path in args.paths:
        headers = {}
        if args.request_id:
            headers["X-Request-ID"] = args.request_id

        response = client.get(path, headers=headers)

        try:
            body = json.dumps(response.json(), sort_keys=True, separators=(",", ":"))
        except Exception:
            body = response.text

        print(f"{response.status_code} {path} {body}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
