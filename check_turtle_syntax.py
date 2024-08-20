# check_turtle_syntax.py
import sys
from rdflib import Graph

def check_syntax(file_path):
    try:
        g = Graph()
        g.parse(file_path, format="turtle")
        print(f"Syntax check passed for {file_path}")
    except Exception as e:
        print(f"Syntax check failed for {file_path}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    for file_path in sys.argv[1:]:
        check_syntax(file_path)
