import os
import sys
import plistlib
import re

def extract_and_write_kerning_groups(fea_file_path: str, output_plist_path: str):
    """
    Extracts kerning groups (glyph class definitions) from a features.fea file
    and writes them to a groups.plist file in UFO format.

    Args:
        fea_file_path (str): The path to the input features.fea file.
        output_plist_path (str): The path where the groups.plist file will be written.
    """
    if not os.path.exists(fea_file_path):
        print(f"Error: Input features.fea file not found at '{fea_file_path}'")
        return

    print(f"Reading features from: {fea_file_path}")
    
    try:
        # First try with fontTools Parser
        try:
            from fontTools.feaLib.parser import Parser
            
            # Read the content of the features.fea file
            with open(fea_file_path, 'r', encoding='utf-8') as f:
                fea_content = f.read()

            # Initialize parser correctly for fontTools 4.x
            # The signature is Parser(text, glyphNames=None, followIncludes=True, **kwargs)
            parser = Parser(fea_content, glyphNames=set(), followIncludes=False)
            parser.parse()

            extracted_groups_data = {}

            # Check if glyphClassDefs exists and has content
            if hasattr(parser, 'glyphClassDefs') and parser.glyphClassDefs:
                print(f"Found {len(parser.glyphClassDefs)} glyph class definitions")
                
                # Iterate through the parsed glyph class definitions
                for class_name, glyph_class_def in parser.glyphClassDefs.items():
                    # Remove '@' prefix if present
                    clean_name = class_name[1:] if class_name.startswith('@') else class_name
                    
                    # Extract glyph names
                    if hasattr(glyph_class_def, 'glyphs'):
                        glyph_list = [g.name.lstrip("\\") if hasattr(g, 'name') else str(g).lstrip("\\") for g in glyph_class_def.glyphs]
                    else:
                        glyph_list = list(glyph_class_def)

                    # Determine kern1 or kern2 based on naming conventions
                    ufo_group_name_prefix = determine_group_type(clean_name)
                    full_ufo_group_name = ufo_group_name_prefix + clean_name
                    
                    extracted_groups_data[full_ufo_group_name] = glyph_list
                    print(f"  Extracted group: {full_ufo_group_name} -> {glyph_list}")
            else:
                print("No glyph class definitions found with fontTools parser, trying regex fallback...")
                raise Exception("No glyphClassDefs found")
                
        except Exception as parser_error:
            print(f"fontTools parsing failed: {parser_error}")
            print("Falling back to regex-based parsing...")
            
            # Fallback to regex-based parsing
            extracted_groups_data = parse_groups_with_regex(fea_file_path)

        if not extracted_groups_data:
            print("No kerning groups were extracted.")
            return

        # Write the groups data directly to a plist file
        with open(output_plist_path, 'wb') as plist_file:
            plistlib.dump(extracted_groups_data, plist_file)
        
        print(f"Successfully wrote {len(extracted_groups_data)} kerning groups to: {output_plist_path}")

    except Exception as e:
        print(f"An error occurred during processing: {e}")
        import traceback
        traceback.print_exc()

def determine_group_type(class_name):
    """Determine if a group should be kern1 or kern2 based on naming conventions."""
    class_name_upper = class_name.upper()
    
    # Common patterns for left-side (kern1) groups
    left_patterns = ['LEFT', 'LHS', 'L_', 'FIRST', '1ST', '_L', 'L.']
    # Common patterns for right-side (kern2) groups  
    right_patterns = ['RIGHT', 'RHS', 'R_', 'SECOND', '2ND', '_R', 'R.']
    
    # Check for right-side patterns first (more specific)
    for pattern in right_patterns:
        if pattern in class_name_upper or class_name_upper.startswith('R'):
            return 'public.kern2.'
    
    # Check for left-side patterns
    for pattern in left_patterns:
        if pattern in class_name_upper or class_name_upper.startswith('L'):
            return 'public.kern1.'
    
    # Default to kern1 if no clear indication
    return 'public.kern1.'

def parse_groups_with_regex(fea_file_path):
    """Fallback regex-based parser for .fea files."""
    extracted_groups_data = {}
    
    with open(fea_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex pattern to match class definitions like:
    # @class_name = [glyph1 glyph2 glyph3];
    class_pattern = r'@(\w+)\s*=\s*\[(.*?)\]\s*;'
    
    matches = re.findall(class_pattern, content, re.DOTALL)
    
    for class_name, glyphs_str in matches:
        # Split glyph names and clean them
        glyph_list = [glyph.strip() for glyph in glyphs_str.split() if glyph.strip()]
        
        if glyph_list:  # Only add non-empty groups
            ufo_group_name_prefix = determine_group_type(class_name)
            full_ufo_group_name = ufo_group_name_prefix + class_name
            extracted_groups_data[full_ufo_group_name] = glyph_list
            print(f"  Extracted group (regex): {full_ufo_group_name} -> {glyph_list}")
    
    return extracted_groups_data

def main():
    # Handle command line arguments
    if len(sys.argv) == 3:
        input_fea_file = sys.argv[1]
        output_plist_file = sys.argv[2]
    elif len(sys.argv) == 1:
        # Default values when no arguments provided
        input_fea_file = 'features.fea'
        output_plist_file = 'groups.plist'
    else:
        print("Usage: python kern-groups.py [input.fea] [output.plist]")
        print("   or: python kern-groups.py  (uses default features.fea and groups.plist)")
        sys.exit(1)
    
    extract_and_write_kerning_groups(input_fea_file, output_plist_file)

if __name__ == "__main__":
    main()
