"""
Roll Draft Simulator - Hint Generation
Analyzes unit selections and provides hints based on Legion TD 2's autopicker logic
"""

import xml.etree.ElementTree as ET

# Cache for parsed XML data
_units_xml_cache = None


def parse_units_xml():
    """Parse units.xml and return a dictionary of unit data (cached)"""
    global _units_xml_cache
    
    if _units_xml_cache is not None:
        return _units_xml_cache
    
    tree = ET.parse('Files/json/units.xml')
    root = tree.getroot()
    
    units_dict = {}
    for unit in root.findall('unit'):
        unit_id = unit.get('id')
        unit_data = {'unitId': unit_id}
        
        for child in unit:
            tag = child.tag
            text = child.text or ''
            
            # Parse the value after :::
            if ':::' in text:
                parts = text.split(':::')
                value = parts[-1] if len(parts) > 1 else ''
            else:
                value = text
            
            # Store relevant fields
            if tag == 'isenabled':
                unit_data['isEnabled'] = value == 'True'
            elif tag == 'infotier':
                unit_data['infoTier'] = f'Tier-{value}' if value else None
            elif tag == 'upgradesfrom':
                # Empty string or list means no upgrade (base unit)
                unit_data['upgradesFrom'] = value if value else None
            elif tag == 'goldcost':
                unit_data['goldCost'] = value
            elif tag == 'name':
                unit_data['name'] = value
            elif tag == 'iconpath':
                unit_data['iconPath'] = value
            elif tag == 'legion':
                unit_data['legionId'] = value
            elif tag == 'mm_groups':
                # Parse flags like: mm_dps,mm_tank,mm_arcane
                # Filter out empty strings
                unit_data['mm_groups'] = [g.strip() for g in value.split(',') if g.strip()] if value else []
            elif tag == 'mm_rec_groups':
                # Parse recommender override groups
                unit_data['mm_rec_groups'] = [g.strip() for g in value.split(',') if g.strip()] if value else []
            elif tag == 'totalvalue':
                unit_data['totalValue'] = value
        
        units_dict[unit_id] = unit_data
    
    _units_xml_cache = units_dict
    return units_dict


def calculate_roll_hints(unit_ids, selected_indices):
    """
    Calculate hints for a roll selection based on Legion TD 2 autopicker logic
    
    Args:
        unit_ids: List of 10 unit IDs in the roll
        selected_indices: List of indices of selected units (1-6 units)
    
    Returns:
        List of hint strings (e.g., "⚠️ No Tank", "Nice Roll 👍")
    """
    if len(unit_ids) != 10:
        return ['⚠️ Invalid roll: Expected 10 units']
    
    # Load units data from XML
    units_xml = parse_units_xml()
    
    # Get only the selected units (units that player chose)
    selected_units = [units_xml.get(unit_ids[i]) for i in selected_indices 
                     if i < len(unit_ids) and unit_ids[i] and units_xml.get(unit_ids[i])]
    
    hints = []
    
    # Track properties
    has_t1 = False
    has_t2_or_t3 = False
    has_t3_t4_or_t5 = False
    has_t5_or_t6 = False
    has_magic = False
    has_pierce = False
    has_impact = False
    has_arcane = False
    has_tank = False
    has_dps = False
    has_fortified_or_natural = False
    has_swift_or_natural = False
    tier_counts = {}
    
    for unit in selected_units:
        if not unit:
            continue
        
        # Get mm_groups - use mm_rec_groups if available (for autopicker), otherwise mm_groups
        mm_groups = set(unit.get('mm_rec_groups', []))

        for g in unit.get('mm_groups', []):
            mm_groups.add(g)
            
        # Check tier
        tier = unit.get('infoTier', '')
        if tier:
            tier_num = tier.replace('Tier-', '')
            tier_counts[tier_num] = tier_counts.get(tier_num, 0) + 1
            
            if tier == 'Tier-1':
                has_t1 = True
            if tier in ['Tier-2', 'Tier-3']:
                has_t2_or_t3 = True
            if tier in ['Tier-3', 'Tier-4', 'Tier-5']:
                has_t3_t4_or_t5 = True
            if tier in ['Tier-5', 'Tier-6']:
                has_t5_or_t6 = True
        
        # Check attack types using mm_groups
        if 'mm_magic' in mm_groups:
            has_magic = True
        if 'mm_pierce' in mm_groups:
            has_pierce = True
        if 'mm_impact' in mm_groups:
            has_impact = True
        
        # Check armor types using mm_groups
        if 'mm_arcane' in mm_groups:
            has_arcane = True
        
        # Check fortified/natural and swift/natural (doesn't require tank)
        if 'mm_fort_or_nat' in mm_groups:
            has_fortified_or_natural = True
        if 'mm_swift_or_nat' in mm_groups:
            has_swift_or_natural = True
        
        # Check tank/DPS using mm_groups
        if 'mm_tank' in mm_groups:
            has_tank = True
        #print(unit)
        #print(mm_groups)
        if 'mm_dps' in mm_groups:
            has_dps = True
    
    # Generate hints based on conditions (in priority order)
    if not has_tank:
        hints.append('⚠️ No Tank')
    if not has_dps:
        hints.append('⚠️ No DPS')
    if not has_t1:
        hints.append('⚠️ No T1s')
    if not has_t3_t4_or_t5:
        hints.append('⚠️ Not Enough Mid-Tier Fighters')
    if not has_t5_or_t6:
        hints.append('⚠️ Not Enough High-Tier Fighters')
    if not has_magic:
        hints.append('⚠️ No Magic')
    if not has_pierce:
        hints.append('⚠️ No Pierce')
    if not has_impact:
        hints.append('⚠️ No Impact')
    if not has_arcane:
        hints.append('⚠️ No Arcane')
    if not has_fortified_or_natural:
        hints.append('⚠️ No Fortified/Natural')
    if not has_swift_or_natural:
        hints.append('⚠️ No Swift/Natural')
    
    # Check for too many of same tier (4 or more)
    for tier_num, count in tier_counts.items():
        if count >= 4:
            hints.append('⚠️ Too Many Same Tier')
            break
    
    # If no hints, it's a nice roll!
    if not hints:
        hints.append('Nice Roll 👍')
    
    return hints

