import os
from pathlib import Path
import uvicorn

if __name__=='__main__':
    from .config import DATA_DIR
    os.environ.setdefault('PYTHONPYCACHEPREFIX',str(DATA_DIR/'cache'/'python'))
    uvicorn.run('personal_agent.app:app',host='127.0.0.1',port=int(os.environ.get('PERSONAL_AGENT_PORT','8765')),access_log=False,log_level='warning')
