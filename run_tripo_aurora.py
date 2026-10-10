"""
run_tripo_aurora.py
Generic runner for multiview or task-based 3D reconstruction pipelines.
Polls task, downloads GLB, and converts to all formats (GLB, OBJ, STL, FBX, .blend).

Usage:
    python run_tripo_aurora.py [TASK_ID] [MODEL_NAME]
"""

import sys
import os
from pipeline import run_pipeline

DEFAULT_TASK_ID = "c22c343c-8472-4365-91be-ad3e913e32cd"

def main():
    task_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK_ID
    model_name = sys.argv[2] if len(sys.argv) > 2 else "aurora_robot"

    print(f"[*] Processing 3D task: {task_id} -> {model_name}")
    run_pipeline(task=task_id, name=model_name)

if __name__ == "__main__":
    main()
