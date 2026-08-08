from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.analysis_job import AnalysisJobRecord
from app.schemas import AnalysisJob


class AnalysisJobRepository:
    """分析任务的唯一数据访问入口，Service 不直接接触 ORM 实体。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, job: AnalysisJob) -> AnalysisJob:
        record = AnalysisJobRecord(
            id=job.id,
            video_id=job.video_id,
            status=job.status.value,
            stage=job.stage,
            progress=job.progress,
            detail=job.detail,
            result=job.result.model_dump(mode="json") if job.result else None,
            error_code=job.error_code,
        )
        self._session.add(record)
        self._session.flush()
        return self._to_schema(record)

    def get(self, job_id: str) -> AnalysisJob | None:
        record = self._session.get(AnalysisJobRecord, job_id)
        return self._to_schema(record) if record else None

    def update(self, job_id: str, values: dict[str, Any]) -> AnalysisJob:
        record = self._session.get(AnalysisJobRecord, job_id)
        if record is None:
            raise LookupError(f"分析任务不存在: {job_id}")
        for key, value in values.items():
            if key == "status" and hasattr(value, "value"):
                value = value.value
            if key == "result" and value is not None:
                value = value.model_dump(mode="json")
            setattr(record, key, value)
        self._session.flush()
        return self._to_schema(record)

    def fail_interrupted(self) -> int:
        """服务重启后，旧进程未完成的任务不能继续显示为处理中。"""
        statement = select(AnalysisJobRecord).where(
            AnalysisJobRecord.status.in_(["queued", "processing"])
        )
        records = list(self._session.scalars(statement))
        for record in records:
            record.status = "failed"
            record.stage = "任务已中断"
            record.progress = 0
            record.detail = "分析服务曾重启，请在片库中重新提交该视频。"
            record.error_code = "SERVICE_RESTARTED"
        self._session.flush()
        return len(records)

    @staticmethod
    def _to_schema(record: AnalysisJobRecord) -> AnalysisJob:
        # Repository 在边界处转回 Pydantic，避免 ORM 实体泄漏到 Service 或 Controller。
        return AnalysisJob.model_validate(
            {
                "id": record.id,
                "video_id": record.video_id,
                "status": record.status,
                "stage": record.stage,
                "progress": record.progress,
                "detail": record.detail,
                "result": record.result,
                "error_code": record.error_code,
            }
        )
