#!/bin/bash
cd /Users/chenleiv/signal-forge

CHANGED=$(git status --porcelain)

# Frontend validation — runs on TS/HTML/SCSS changes
if echo "$CHANGED" | grep -qE '\.(ts|html|scss)$'; then
  cd frontend && npm run build > /tmp/sf-build.log 2>&1
  BUILD_EXIT=$?
  cd ..

  if [ $BUILD_EXIT -ne 0 ]; then
    python3 -c "
import json
log = open('/tmp/sf-build.log').read()[-2000:]
output = {
    'hookSpecificOutput': {
        'hookEventName': 'Stop',
        'additionalContext': 'FRONTEND BUILD FAILED. Fix these errors before marking COMPLETE:\n' + log
    }
}
print(json.dumps(output))
"
    exit 0
  fi
fi

# Backend validation — runs on Python changes
if echo "$CHANGED" | grep -qE '\.py$'; then
  cd backend && python -m pytest --tb=short -q > /tmp/sf-pytest.log 2>&1
  PYTEST_EXIT=$?
  cd ..

  if [ $PYTEST_EXIT -ne 0 ]; then
    python3 -c "
import json
log = open('/tmp/sf-pytest.log').read()[-2000:]
output = {
    'hookSpecificOutput': {
        'hookEventName': 'Stop',
        'additionalContext': 'BACKEND TESTS FAILED. Fix these errors before marking COMPLETE:\n' + log
    }
}
print(json.dumps(output))
"
    exit 0
  fi
fi

exit 0
