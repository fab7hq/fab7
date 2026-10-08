#!/bin/sh
# Muse takes one script per hook; each runs the one shim with its hook's name.
exec sh "$(dirname "$0")/weft-signal" muse PermissionRequest
