from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
import os
import subprocess
from app.models.common import Result
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ResourceItem(BaseModel):
    type: str
    value: str
    name: str

class OpenResourceRequest(BaseModel):
    resources: List[ResourceItem]

@router.post("/open")
async def open_resources(request: OpenResourceRequest) -> Result[dict]:
    opened = []
    failed = []

    for res in request.resources:
        path = res.value.strip()
        if not path:
            continue
            
        try:
            if res.type == 'url':
                # Open URL in default browser
                if os.name == 'nt':
                    os.startfile(path)
                else:
                    subprocess.Popen(['open' if os.sys.platform == 'darwin' else 'xdg-open', path])
                opened.append(res.name)
            
            elif res.type in ['folder', 'file', 'app']:
                # Open file/folder/app using default associated program
                if os.path.exists(path):
                    if os.name == 'nt':
                        os.startfile(path)
                    else:
                        subprocess.Popen(['open' if os.sys.platform == 'darwin' else 'xdg-open', path])
                    opened.append(res.name)
                else:
                    failed.append(f"{res.name} (Not found)")
            
            elif res.type == 'script':
                # Execute script
                if os.path.exists(path):
                    if os.name == 'nt':
                        subprocess.Popen(['cmd.exe', '/c', 'start', 'cmd.exe', '/k', path])
                    else:
                        subprocess.Popen(['sh', path])
                    opened.append(res.name)
                else:
                    failed.append(f"{res.name} (Not found)")
                    
        except Exception as e:
            logger.error(f"Failed to open {path}: {e}")
            failed.append(f"{res.name} ({str(e)})")

    if failed:
        return Result.fail(message=f"Opened {len(opened)} items. Failed: {', '.join(failed)}")
    
    return Result.ok(data={"opened": opened}, message=f"Successfully opened {len(opened)} resources.")