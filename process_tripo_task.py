"""
process_tripo_task.py
Monitors a Tripo 3D task, downloads the generated model,
and automatically exports it to all formats (GLB, OBJ, STL, FBX, and Blender .blend).

Usage:
    python process_tripo_task.py [TASK_ID] [MODEL_NAME]
"""

import sys
import os
from pipeline import run_pipeline

DEFAULT_TASK_ID = "9d2e5aff-f301-41da-9002-6c5acff6b308"

def main():
    task_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK_ID
    model_name = sys.argv[2] if len(sys.argv) > 2 else f"model_{task_id[:8]}"

    print(f"[*] Processing Tripo task: {task_id}")
    run_pipeline(task=task_id, name=model_name)

if __name__ == "__main__":
    main()
