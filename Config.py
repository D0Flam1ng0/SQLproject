TABLE_NAME = "Characters"

# Define columns for the 'Characters' table for generic CRUD.
# 'creature_name' is the name of the character (from Creatures table).
# 'gold' is the gold amount (from Characters table).
# The primary key 'character_id' (or 'id' as used in the generic functions)
# is handled separately and not listed here for form inputs.
COLUMNS = {
    "creature_name": "TEXT", # This will be the character's name
    "gold": "INTEGER"        # This will be the character's gold
}
