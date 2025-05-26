import os
import inspect # Import the inspect module
from fontTools.feaLib.parser import Parser

# Create a dummy .fea file for testing
dummy_fea_content = """
feature kern {
    pos A V -50;
} kern;
"""
dummy_fea_path = "dummy.fea"
with open(dummy_fea_path, 'w', encoding='utf-8') as f:
    f.write(dummy_fea_content)

print(f"Testing Parser with glyphSet in {os.getcwd()}")
print(f"FontTools Parser location: {inspect.getfile(Parser)}") # Added for debug

try:
    # A minimal set of glyph names, including 'A' and 'V'
    test_glyph_set = {'A', 'V', 'B', 'C'} 
    
    # --- Inspect Parser arguments ---
    try:
        signature = inspect.signature(Parser.__init__)
        print(f"Parser __init__ parameters: {list(signature.parameters.keys())}")
        if 'glyphSet' in signature.parameters:
            print("'glyphSet' parameter IS found in Parser signature.")
        else:
            print("'glyphSet' parameter is NOT found in Parser signature.")
    except Exception as sig_e:
        print(f"Could not inspect Parser signature: {sig_e}")
    # --- End inspect ---

    with open(dummy_fea_path, 'r', encoding='utf-8') as f:
        parser = Parser(f, dummy_fea_path, glyphSet=test_glyph_set, followIncludes=False)
        print("SUCCESS: fontTools.feaLib.parser.Parser accepts 'glyphSet' argument (instantiation succeeded).")
        parser.parse()
        print("SUCCESS: Dummy .fea file parsed.")
    
except TypeError as e:
    if "'glyphSet'" in str(e):
        print(f"ERROR: Parser does NOT accept 'glyphSet' argument. Details: {e}")
        print("This indicates a deep issue with your fontTools installation or environment.")
    else:
        print(f"ERROR: A TypeError occurred, but not related to 'glyphSet': {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if os.path.exists(dummy_fea_path):
        os.remove(dummy_fea_path)
