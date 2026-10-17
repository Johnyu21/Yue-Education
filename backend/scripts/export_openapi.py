import argparse,json
from pathlib import Path
from app.main import app
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(app.openapi(),ensure_ascii=False,indent=2),encoding='utf-8');print('OpenAPI exported:',target)
