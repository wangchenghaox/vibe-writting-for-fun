"""
Task管理器 - 管理任务的创建、跟踪和执行
"""
from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class Task:
    def __init__(self, task_id: str, description: str):
        self.id = task_id
        self.description = description
        self.status = TaskStatus.PENDING
        self.result: Optional[str] = None

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def create_task(self, task_id: str, description: str) -> Task:
        """创建任务"""
        task = Task(task_id, description)
        self.tasks[task_id] = task
        logger.info(f"创建任务: {task_id}")
        return task

    def update_status(self, task_id: str, status: TaskStatus):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            logger.info(f"任务 {task_id} 状态更新为 {status.value}")

    def set_result(self, task_id: str, result: str):
        """设置任务结果"""
        if task_id in self.tasks:
            self.tasks[task_id].result = result
            self.tasks[task_id].status = TaskStatus.COMPLETED

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Task]:
        """列出所有任务"""
        return list(self.tasks.values())
