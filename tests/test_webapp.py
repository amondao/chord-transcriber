# -*- coding: utf-8 -*-
"""webapp.py を Flask の test_client で検証する（実サーバー起動は不要）。

  python tests/test_webapp.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webapp import app

DEMO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo.wav')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    c = app.test_client()

    r = c.get('/')
    print('GET /        ->', r.status_code, '(HTML', len(r.data), 'bytes)')

    with open(DEMO, 'rb') as f:
        r = c.post('/analyze',
                   data={'file': (f, 'demo.wav'), 'mode': 'standard', 'penalty': '0.3'},
                   content_type='multipart/form-data')
    print('POST /analyze ->', r.status_code)
    d = r.get_json()
    if r.status_code == 200:
        print('  key        :', d['key_name'], '(given=%s)' % d['key_given'])
        print('  progression:', ' | '.join(s['degree'] for s in d['segments']))
        print('  segments   :', len(d['segments']))
    else:
        print('  error:', d)


if __name__ == '__main__':
    main()
