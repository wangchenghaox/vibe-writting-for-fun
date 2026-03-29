import pytest
from app.capability.task_manager import TaskManager, TaskStatus


def test_create_task():
    manager = TaskManager()
    task = manager.create_task("task1", "Test task")
    assert task.status == TaskStatus.PENDING
    assert task.id == "task1"


def test_update_task_status():
    manager = TaskManager()
    task = manager.create_task("task1", "Test task")
    manager.update_status("task1", TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED
