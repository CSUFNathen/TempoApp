# config.py
import os

APP_TITLE = "Server Control"

# Window
WINDOW_GEOMETRY = "900x650"
WINDOW_ALPHA = 0.9

# Java memory defaults
DEFAULT_MIN_RAM = "2G"
DEFAULT_MAX_RAM = "2G"

# Jar discovery (used by ServerController.find_jar)
JAR_GLOB = "FabricServer.jar"
WORKDIR = os.path.abspath(os.getcwd())

# Players tab behavior
TIMEOUT_MINUTES = 10          # if you re-enable timeout later
PLAYER_LIST_POLL_SECS = 15    # run "list" every N seconds
