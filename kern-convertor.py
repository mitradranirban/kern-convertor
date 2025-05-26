import os
import argparse
from fontTools.feaLib.parser import Parser
# Corrected import: Removed GlyphList as it's not a direct importable member of feaLib.ast
from fontTools.feaLib.ast import FeatureFile, LookupBlock, ValueRecord, Anchor, MarkBasePosStatement, MarkMarkPosStatement, PairPosStatement, GlyphClassDefinition, GlyphName, GlyphClass # Added GlyphClass for explicit type checking
from fontTools.ttLib import TTFont
import plistlib
import logging

# Set up logging for better feedback
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get_all_glyph_names_from_font(font_path):
    """
    Extracts all glyph names from a given font file.
    """
    try:
        font = TTFont(font_path)
        glyph_names = set(font.getGlyphOrder())
        font.close()
        return glyph_names
    except Exception as e:
        logging.error(f"Failed to read glyph names from font '{font_path}': {e}")
        return None

def extract_glyph_names_from_group(group):
    """
    Extract glyph names from a glyph group object.
    """
    resolved_glyphs = []
    
    if hasattr(group, 'as_list'):
        resolved_glyphs = [g.asFea() if hasattr(g, 'asFea') else str(g) for g in group.as_list]
    elif hasattr(group, 'glyphs'):
        resolved_glyphs = [g.asFea() if hasattr(g, 'asFea') else str(g) for g in group.glyphs]
    elif isinstance(group, GlyphName):
        resolved_glyphs = [group.asFea()]
    elif hasattr(group, '__iter__') and not isinstance(group, str):
        resolved_glyphs = [g.asFea() if hasattr(g, 'asFea') else str(g) for g in group]
    elif hasattr(group, 'asFea'):
        resolved_glyphs = [group.asFea()]
    else:
        logging.warning(f"Unexpected group structure: {type(group)}")
    
    return resolved_glyphs

def extract_glyphs_from_glyphclass(glyph_class, glyph_classes_dict):
    """
    Recursively extract glyph names from a GlyphClass object.
    """
    member_glyphs = []
    
    # Check if glyph_class has glyphs attribute
    if hasattr(glyph_class, 'glyphs'):
        glyphs_list = glyph_class.glyphs
        # Handle different possible structures
        if hasattr(glyphs_list, 'glyphs'):
            # It's a GlyphClass with nested glyphs
            items = glyphs_list.glyphs
        elif hasattr(glyphs_list, '__iter__'):
            # It's directly iterable
            items = glyphs_list
        else:
            logging.warning(f"Unexpected glyph class structure: {type(glyphs_list)}")
            return []
    else:
        logging.warning(f"GlyphClass object has no 'glyphs' attribute: {glyph_class}")
        return []
    
    for item in items:
        if isinstance(item, GlyphName):
            # If it's an individual glyph name, add its string representation
            member_glyphs.append(item.asFea())
        elif isinstance(item, GlyphClass):
            # If it's a nested glyph class, try to expand it
            nested_class_name = item.asFea()
            if nested_class_name in glyph_classes_dict:
                member_glyphs.extend(glyph_classes_dict[nested_class_name])
                logging.debug(f"Expanded nested class '{nested_class_name}'.")
            else:
                logging.warning(f"Nested glyph class '{nested_class_name}' not yet defined. Adding class name directly.")
                member_glyphs.append(nested_class_name)
        elif isinstance(item, str):
            # Handle string glyph names directly
            member_glyphs.append(item)
        elif hasattr(item, 'asFea'):
            # Generic handling for other AST nodes that can be converted to FEA syntax
            member_glyphs.append(item.asFea())
        else:
            logging.warning(f"Unknown item type {type(item).__name__} in glyph class. Skipping.")
    
    return member_glyphs

def convert_kerning_fea_to_plist(fea_file_path, output_plist_path, font_path=None):
    """
    Converts kerning rules from a .fea file to a kerning.plist format.
    Handles class-based kerning by expanding classes.
    """
    logging.info(f"Attempting to convert '{fea_file_path}' to '{output_plist_path}'...")

    if not os.path.exists(fea_file_path):
        logging.error(f"Input file not found: '{fea_file_path}'")
        return

    all_glyph_names = None
    if font_path:
        logging.info(f"Checking for input font file: '{font_path}'")
        if not os.path.exists(font_path):
            logging.warning(f"Font file not found: '{font_path}'. Proceeding without glyph set validation. This might lead to unexpected parsing issues if glyphs are not recognized.")
        else:
            all_glyph_names = get_all_glyph_names_from_font(font_path)
            if all_glyph_names is None:
                logging.warning("Could not retrieve glyph names from font. Proceeding without glyph set for parser.")
    
    # If font_path was not provided or failed, provide an empty set
    if all_glyph_names is None:
        logging.info("Proceeding without a pre-defined glyph set for the parser. Parser will infer glyphs from the .fea file.")
        all_glyph_names = set()

    feature_file = None
    try:
        logging.info("Parsing .fea file...")
        with open(fea_file_path, 'r', encoding='utf-8') as f:
            parser = Parser(
                featurefile=f,
                glyphNames=all_glyph_names,
                followIncludes=False # Set to True if your .fea uses 'include' statements.
            )
            feature_file = parser.parse()
        logging.info("Finished parsing .fea file.")

    except Exception as e:
        logging.error(f"Error parsing .fea file: {e}")
        return

    # --- Store Glyph Class Definitions ---
    glyph_classes = {} # Stores {'@ClassName': ['glyph1', 'glyph2', ...]}
    if feature_file:
        for statement in feature_file.statements:
            if isinstance(statement, GlyphClassDefinition):
                class_name = statement.name
                
                # Use the helper function to extract glyphs
                member_glyphs = extract_glyphs_from_glyphclass(statement, glyph_classes)
                
                glyph_classes[class_name] = member_glyphs
                logging.info(f"Identified glyph class: {class_name} with {len(member_glyphs)} members.")
    # --- End New Logic ---

    # Initialize a dictionary for kerning
    kerning_data = {}

    if feature_file:
        # Iterate through all lookup blocks in the parsed feature file
        for lookup_block in feature_file.statements:
            # We are interested in `lookup_block`s as well as direct `feature` blocks
            # Feature blocks themselves contain statements, but for kerning, we often find PairPosStatements
            # inside LookupBlocks that are then referenced by a feature.
            # We must iterate through all top-level statements, and if they are Lookups, then their statements.
            
            statements_to_process = []
            if isinstance(lookup_block, LookupBlock) and lookup_block.name.lower().startswith('kern'):
                logging.info(f"Processing kerning lookup: {lookup_block.name}")
                statements_to_process = lookup_block.statements
            # Add logic here if kerning rules are directly under a 'feature kern' block
            # This current structure assumes PairPosStatement inside LookupBlocks.

            for statement in statements_to_process:
                if isinstance(statement, PairPosStatement):
                    try:
                        # PairPosStatement attributes are different - they use 'glyphs1' and 'glyphs2'
                        first_group = getattr(statement, 'glyphs1', None) or getattr(statement, 'firstGlyphs', None)
                        second_group = getattr(statement, 'glyphs2', None) or getattr(statement, 'secondGlyphs', None)
                        
                        if first_group is None or second_group is None:
                            logging.warning(f"Could not find glyph groups in PairPosStatement: {statement}")
                            continue
                        
                        value = 0
                        if hasattr(statement, 'valuerecord1') and statement.valuerecord1 and statement.valuerecord1.xAdvance is not None:
                            value = statement.valuerecord1.xAdvance
                        elif hasattr(statement, 'value1') and statement.value1 and statement.value1.xAdvance is not None:
                            value = statement.value1.xAdvance
                        
                        # Resolve first group (individual glyphs or expanded class)
                        resolved_first_glyphs = []
                        if hasattr(first_group, 'is_class') and first_group.is_class:
                            class_name = first_group.asFea()
                            resolved_first_glyphs = glyph_classes.get(class_name, [])
                            if not resolved_first_glyphs:
                                logging.warning(f"Class '{class_name}' used in kerning but not defined. Skipping kerning for this class.")
                                continue
                        else:
                            # Handle different possible structures for first_group
                            resolved_first_glyphs = extract_glyph_names_from_group(first_group)

                        # Resolve second group (individual glyphs or expanded class)
                        resolved_second_glyphs = []
                        if hasattr(second_group, 'is_class') and second_group.is_class:
                            class_name = second_group.asFea()
                            resolved_second_glyphs = glyph_classes.get(class_name, [])
                            if not resolved_second_glyphs:
                                logging.warning(f"Class '{class_name}' used in kerning but not defined. Skipping kerning for this class.")
                                continue
                        else:
                            # Handle different possible structures for second_group
                            resolved_second_glyphs = extract_glyph_names_from_group(second_group)

                        # Generate all individual kerning pairs
                        for g1 in resolved_first_glyphs:
                            for g2 in resolved_second_glyphs:
                                if g1 not in kerning_data:
                                    kerning_data[g1] = {}
                                kerning_data[g1][g2] = value
                                logging.debug(f"Added kerning pair: {g1} {g2} {value}")

                    except AttributeError as ae:
                        logging.warning(f"Could not extract kerning from statement due to missing attribute ({ae}): {statement}. Skipping.")
                        continue
                    except Exception as ex:
                        logging.warning(f"Generic error processing PairPosStatement {statement}: {ex}. Skipping.")
                        continue
                elif isinstance(statement, (MarkBasePosStatement, MarkMarkPosStatement)):
                    # These are typically for mark positioning, not direct kerning.
                    logging.debug(f"Skipping mark positioning statement type: {type(statement).__name__}")
                else:
                    logging.debug(f"Skipping non-PairPosStatement type in kern lookup: {type(statement).__name__}")

    if not kerning_data:
        logging.warning("No kerning data extracted from .fea file. Output plist will be empty.")
        # This warning might still occur if your .fea file contains GPOS kerning
        # but it's not structured as PairPosStatement in a 'kern' lookup,
        # or if class definitions are incorrect.

    try:
        # Save the kerning data to a .plist file
        with open(output_plist_path, 'wb') as fp:
            plistlib.dump(kerning_data, fp)
        logging.info(f"Successfully converted kerning to '{output_plist_path}'")
    except Exception as e:
        logging.error(f"Error writing to plist file '{output_plist_path}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Convert kerning rules from .fea to kerning.plist.")
    parser.add_argument("fea_file", help="Path to the input .fea file.")
    parser.add_argument("output_plist", help="Path to the output .plist file (e.g., kerning.plist).")
    parser.add_argument("--font", help="Optional: Path to the font file (.ttf, .otf) to extract glyph names for parser validation.", default=None)

    args = parser.parse_args()

    convert_kerning_fea_to_plist(args.fea_file, args.output_plist, args.font)

if __name__ == "__main__":
    main()
