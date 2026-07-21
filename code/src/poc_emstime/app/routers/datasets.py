from fastapi import APIRouter

from poc_emstime.app import config
from poc_emstime.app.schemas import DatasetOption

router = APIRouter()


@router.get("/datasets", response_model=list[DatasetOption])
def list_datasets() -> list[DatasetOption]:
    return [
        DatasetOption(key=o.key, label=o.label, target_col=o.target_col, tq_col=o.tq_col, available=o.available)
        for o in config.list_datasets()
    ]
