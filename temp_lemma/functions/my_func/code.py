#input_type_name: MyFuncInput
#output_type_name: MyFuncResult
#function_name: my_func

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class MyFuncInput(BaseModel):
    # TODO: define the inputs this function takes.
    message: str


class MyFuncResult(BaseModel):
    ok: bool


async def my_func(ctx: FunctionContext, data: MyFuncInput) -> MyFuncResult:
    pod = Pod.from_env()  # authenticated as this function's workload principal
    # TODO: implement. e.g. pod.table("items").create({...})
    return MyFuncResult(ok=True)
