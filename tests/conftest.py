import os


# Test collection should not import TensorFlow through transformers/sentence-transformers.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
