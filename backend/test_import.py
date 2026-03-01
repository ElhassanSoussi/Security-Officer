import sys
print(f"Python executable: {sys.executable}")
print(f"Sys Path: {sys.path}")
try:
    import pypdf
    print(f"pypdf file: {pypdf.__file__}")
except ImportError as e:
    print(f"ImportError: {e}")
