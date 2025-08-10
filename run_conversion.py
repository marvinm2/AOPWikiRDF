#!/usr/bin/env python3
"""
Wrapper script to run AOP-Wiki XML to RDF conversion with configurable output directory.
This allows testing the Python version alongside the Jupyter notebook version.
"""

import sys
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run AOP-Wiki XML to RDF conversion')
    parser.add_argument('--output-dir', default='data/', 
                       help='Output directory for generated files (default: data/)')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Read the conversion script
    with open('AOP-Wiki_XML_to_RDF_conversion.py', 'r') as f:
        script_content = f.read()
    
    # Replace the DATA_DIR configuration
    script_content = script_content.replace(
        "DATA_DIR = 'data/'", 
        f"DATA_DIR = '{args.output_dir}'"
    )
    
    # Replace logging level if specified
    if args.log_level != 'INFO':
        script_content = script_content.replace(
            "level=logging.INFO",
            f"level=logging.{args.log_level}"
        )
    
    # Execute the modified script with proper global namespace
    exec(compile(script_content, 'AOP-Wiki_XML_to_RDF_conversion.py', 'exec'), globals())

if __name__ == '__main__':
    main()