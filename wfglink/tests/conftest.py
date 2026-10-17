import os

# Qt tests run headless everywhere (the container has no display; on a Mac this keeps
# test windows from appearing).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
