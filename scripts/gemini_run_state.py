"""Workflow gates and post-publication activation. No credentials are persisted."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

OPERATIONS = ('preflight', 'preview', 'publish', 'publish-and-enable')


def gate(config, event, operation):
    if event == 'schedule':
        enabled = config.get('dailyEnabled') is True and bool(config.get('lastVerifiedCommit'))
        return dict(generate=enabled, publish=enabled, activate=False)
    if event != 'workflow_dispatch' or operation not in OPERATIONS:
        return dict(generate=False, publish=False, activate=False)
    return dict(generate=operation != 'preflight', publish=operation in ('publish', 'publish-and-enable'), activate=operation == 'publish-and-enable')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['gate', 'activate', 'disable'])
    a = p.parse_args()
    path = Path('config/gemini-automation.json')
    config = json.loads(path.read_text())
    if a.action == 'gate':
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        result = gate(config, os.environ['GITHUB_EVENT_NAME'], event.get('inputs', {}).get('operation', 'preflight'))
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            for key, value in result.items():
                out.write(f'{key}={str(value).lower()}\n')
        print('Generation:', result['generate'], 'Publication:', result['publish'], 'Activate after verification:', result['activate'])
    else:
        # Called only after exact production-byte verification in the workflow.
        if a.action == 'disable':
            config['dailyEnabled'] = False
        else:
            config.update(dailyEnabled=True, lastVerifiedCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), lastVerifiedAt=datetime.now(timezone.utc).isoformat())
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
