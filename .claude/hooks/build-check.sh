#!/bin/bash
cd /Users/chenleiv/signal-forge

# Skip if no frontend TypeScript/HTML/SCSS files changed
git status --porcelain | grep -qE '\.(ts|html|scss)$' || exit 0

# Run build and capture output
cd frontend && npm run build > /tmp/sf-build.log 2>&1
BUILD_EXIT=$?

# Build passed - exit cleanly
[ $BUILD_EXIT -eq 0 ] && exit 0

# Build failed - inject error back into Claude's context
python3 -c "
import json
log = open('/tmp/sf-build.log').read()[-2000:]
output = {
    'hookSpecificOutput': {
        'hookEventName': 'Stop',
        'additionalContext': 'BUILD FAILED. Fix these errors before marking COMPLETE:\n' + log
    }
}
print(json.dumps(output))
"
