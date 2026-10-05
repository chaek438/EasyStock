"""Cross-platform launcher. Run with the installed virtualenv Python."""
import argparse
import sys
from pathlib import Path

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'backend'))
from easystock import create_app
from easystock.models import db
from easystock.seed import seed_demo
from waitress import serve

parser=argparse.ArgumentParser(description='EasyStock local server')
parser.add_argument('--demo',action='store_true',help='Create demo accounts/data if database has no users')
parser.add_argument('--port',type=int,default=5000)
args=parser.parse_args()
if not (root/'frontend'/'dist'/'index.html').exists():
    print('Frontend missing. Run: cd frontend && npm ci && npm run build',file=sys.stderr)
    raise SystemExit(1)
app=create_app()
with app.app_context():
    db.create_all()
    if args.demo:
        if seed_demo(): print('Demo: admin@easystock.local / DemoStock2026!')
        else: print('Existing database preserved; demo seed skipped.')
print(f'EasyStock: http://127.0.0.1:{args.port}',flush=True)
serve(app,host='127.0.0.1',port=args.port,threads=4)
