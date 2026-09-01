"""Every operation is named by hand, because the generated client reads these names."""

from wiener_api.main import create_app


def test_every_operation_is_named_by_hand():
    """FastAPI's default id is `{function}_{path}_{method}`, so `/overview` would reach the
    generated client as `run_overview_api_runs__run_id__overview_get`. `mendel-api` has held
    this list since Plan 3A and Wiener has never had one; W2 adds two routes, which is the
    moment to add the guard rather than the moment to notice it is missing.

    **Held literally.** Adding a route means editing this dict, which is the point: an
    `operation_id` is a name in somebody else's source tree after `make client` runs.
    """
    got = {(path, method): operation.get("operationId")
           for path, methods in create_app().openapi()["paths"].items()
           for method, operation in methods.items()}
    assert got == {
        ("/api/artifacts", "post"): "uploadArtifact",
        ("/api/runs", "post"): "submitRun",
        ("/api/runs", "get"): "listRuns",
        ("/api/runs/summary", "get"): "readBoardSummary",
        ("/api/runs/{run_id}", "get"): "readRun",
        ("/api/runs/{run_id}/events", "get"): "readRunEvents",
        ("/api/runs/{run_id}/graph", "get"): "readRunGraph",
        ("/api/runs/{run_id}/overview", "get"): "readOverview",
        ("/api/runs/{run_id}/tasks", "get"): "readTasks",
        ("/api/runs/{run_id}/results", "get"): "readResults",
        ("/api/runs/{run_id}/series", "get"): "readSeries",
        ("/api/runs/{run_id}/timeline", "get"): "readTimeline",
        ("/api/health", "get"): "health",
    }
