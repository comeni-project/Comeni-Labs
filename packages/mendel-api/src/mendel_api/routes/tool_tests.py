"""Prepare registered sanity checks; the browser carries them to the run service.

No registry changes, execution or model calls happen here. Output verification uses the
same expected-file checks as Forge, pinned to the registry and test definition shown.
"""

import base64
import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException
from mendel_compiler import pipeline_file
from mendel_forge.testing import build_test_pipeline, module_files, params_for
from pydantic import BaseModel, ConfigDict, Field

from mendel_api.refusals import REFUSES
from mendel_api.services import bundle, registry
from mendel_api.services.forge_tests import green

router = APIRouter(prefix="/tool-tests", tags=["registry"])


class TestCase(BaseModel):
    name: str
    fingerprint: str
    run_name: str


class TestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract: str = Field(min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=120)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class PreparedTest(BaseModel):
    bundle: str
    params: dict[str, Any]
    run_name: str


class OutputCheck(TestRequest):
    files: list[str] = Field(max_length=50000)


class CheckedOutputs(BaseModel):
    passed: bool
    problems: list[str]


def _description(test, digest: str) -> TestCase:
    fingerprint = hashlib.sha256((digest + test.model_dump_json()).encode()).hexdigest()
    return TestCase(name=test.name, fingerprint=fingerprint,
                    run_name=f"Registry test [{fingerprint}] {test.contract} / {test.name}"[:200])


def _requested(body: TestRequest):
    stack = registry.stack()
    test = next((test for test in stack.tests.get(body.contract, [])
                 if test.name == body.name), None)
    if test is None:
        raise HTTPException(404, "This registered test no longer exists.")
    case = _description(test, registry.digest())
    if body.fingerprint != case.fingerprint:
        raise HTTPException(409, "The registry or test changed. Refresh and run the current check.")
    return stack, test, case


@router.get("", operation_id="listRegisteredTestCases", responses=REFUSES)
def cases(contract: str) -> list[TestCase]:
    stack = registry.stack()
    if not any(tool.id == contract for tool in stack.registry.all()):
        raise HTTPException(404, "No such registered tool.")
    digest = registry.digest()
    return [_description(test, digest) for test in stack.tests.get(contract, [])]


@router.post("/prepare", operation_id="prepareRegisteredTest", responses=REFUSES)
def prepare(body: TestRequest) -> PreparedTest:
    stack, test, case = _requested(body)
    pipeline = build_test_pipeline(test, stack)
    archive = bundle.archive(pipeline_file.dump(pipeline), pipeline, module_files(pipeline, stack))
    return PreparedTest(bundle=base64.b64encode(archive).decode(),
                        params=params_for(test, pipeline),
                        run_name=case.run_name)


@router.post("/check-outputs", operation_id="checkRegisteredTestOutputs", responses=REFUSES)
def check_outputs(body: OutputCheck) -> CheckedOutputs:
    stack, test, _ = _requested(body)
    problems = green(test, stack.registry.get(test.contract).nf_process, body.files)
    return CheckedOutputs(passed=not problems, problems=[problem.says for problem in problems])
