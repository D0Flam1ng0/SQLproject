import streamlit as st
import mysql.connector
from mysql.connector import Error
import pandas as pd # Needed for st.dataframe
import plotly.express as px # For the overview tab (even if not used in this specific "normal" app, good to have)

# --- Database Connection Details ---
# IMPORTANT: Replace with your ACTUAL MySQL database credentials
DB_CONFIG = {
    'host': 'localhost',         # e.g., 'localhost' or '127.0.0.1'
    'user': 'root',              # Your MySQL username
    'password': '',              # Your MySQL password (use '' if no password)
    'database': 'dnd_database'   # The name of your D&D database
}

# --- Generic CRUD Configuration for the TARGET TABLE ---
# For this "normal" app, we'll focus generic CRUD on the 'Characters' table
# and adapt the "transfer age" transaction to "transfer gold" between characters.
TARGET_TABLE_NAME = "Characters"

# Define columns for the 'Characters' table for generic CRUD.
# We'll include 'creature_name' and 'gold' as examples for CRUD.
# Note: 'character_id' is the primary key and is usually auto-managed or linked from 'Creatures'.
# For simplicity in this generic CRUD, we'll treat 'creature_id' as the 'id' for CRUD operations.
# The 'name' column in the UI will map to 'creature_name'.
TARGET_COLUMNS = {
    "creature_name": "TEXT", # Maps to C.creature_name in Creatures table
    "gold": "INTEGER"        # The gold column we added to Characters
    # You could add more columns here if you want to expose them for generic CRUD,
    # but remember 'Characters' table also links to 'Races' and 'Classes' via foreign keys,
    # making truly generic CRUD complex for all columns.
}

@st.cache_resource
def get_connection():
    """Establishes and returns a database connection.
    Uses st.cache_resource to cache the connection for performance."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        st.error(f"Error connecting to MySQL: {e}")
        st.stop() # Stop the app if connection fails
        return None

# --- Generic CRUD Functions (adapted for MySQL and TARGET_TABLE_NAME) ---

def fetch_all_generic():
    """Fetches all rows from the TARGET_TABLE_NAME.
    Specifically adapted for Characters table to join with Creatures for name."""
    conn = get_connection()
    if conn is None:
        return []
    cursor = conn.cursor(dictionary=True) # Returns rows as dictionaries
    try:
        if TARGET_TABLE_NAME == "Characters":
            # For Characters, we need to join with Creatures to get the creature_name
            # and use creature_id as the primary key for display/selection.
            cursor.execute(f"""
                SELECT
                    C.creature_id AS id,
                    C.creature_name AS creature_name,
                    T.gold AS gold
                FROM
                    Creatures AS C
                JOIN
                    {TARGET_TABLE_NAME} AS T ON C.creature_id = T.character_id
                WHERE
                    C.creature_type = 'Character'
                ORDER BY C.creature_name
            """)
        else:
            # Generic fetch for other tables if TARGET_TABLE_NAME changes
            # Assumes 'id' as primary key for simplicity if not 'Characters'
            cursor.execute(f"SELECT * FROM {TARGET_TABLE_NAME} ORDER BY id")
        
        rows = cursor.fetchall()
        return rows
    except Error as e:
        st.error(f"Error fetching data from {TARGET_TABLE_NAME}: {e}")
        return []
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def insert_row_generic(data):
    """Inserts a new row into the TARGET_TABLE_NAME.
    Special handling for 'Characters' as it requires 'Creatures' entry first."""
    conn = get_connection()
    if conn is None:
        return False
    cursor = conn.cursor()
    try:
        conn.start_transaction() # Start transaction for multi-table insert

        if TARGET_TABLE_NAME == "Characters":
            # 1. Insert into Creatures table first
            creature_name = data.get("creature_name")
            gold = data.get("gold", 0) # Default gold to 0 if not provided
            
            if not creature_name:
                raise ValueError("Creature Name is required for a new Character.")

            # Check if creature_name already exists to avoid duplicates
            cursor.execute("SELECT creature_id FROM Creatures WHERE creature_name = %s LIMIT 1", (creature_name,))
            existing_creature = cursor.fetchone()

            if existing_creature:
                st.warning(f"Character '{creature_name}' already exists. Updating existing character's gold.")
                creature_id = existing_creature[0]
                cursor.execute(f"UPDATE {TARGET_TABLE_NAME} SET gold = %s WHERE character_id = %s", (gold, creature_id))
            else:
                # Insert into Creatures
                cursor.execute("""
                    INSERT INTO Creatures (creature_type, creature_name, hit_points, armor_class, speed, size, level, is_homebrew)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, ('Character', creature_name, 50, 10, 30, 'Medium', 1, False))
                creature_id = cursor.lastrowid # Get the ID of the newly inserted creature

                # 2. Insert into Characters table using the new creature_id
                # For simplicity, we'll use default race/class IDs. You might want to add select boxes for these.
                cursor.execute("SELECT race_id FROM Races WHERE race_name = 'Human' LIMIT 1")
                default_race_id = cursor.fetchone()[0] if cursor.rowcount > 0 else 1
                cursor.execute("SELECT class_id FROM Classes WHERE class_name = 'Fighter' LIMIT 1")
                default_class_id = cursor.fetchone()[0] if cursor.rowcount > 0 else 1

                cursor.execute(f"""
                    INSERT INTO {TARGET_TABLE_NAME} (character_id, race_id, class_id, gold)
                    VALUES (%s, %s, %s, %s)
                """, (creature_id, default_race_id, default_class_id, gold))
            
            conn.commit()
            st.success(f"Character '{creature_name}' added/updated successfully!")

        else:
            # Generic insert for other tables
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            query = f"INSERT INTO {TARGET_TABLE_NAME} ({columns}) VALUES ({placeholders})"
            cursor.execute(query, tuple(data.values()))
            conn.commit()
            st.success(f"Record added to {TARGET_TABLE_NAME} successfully!")
        
        return True
    except Error as e:
        st.error(f"Error inserting data into {TARGET_TABLE_NAME}: {e}")
        conn.rollback()
        return False
    except ValueError as e:
        st.error(f"Validation Error: {e}")
        conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def update_row_generic(pk_val, data):
    """Updates an existing row in the TARGET_TABLE_NAME based on its primary key.
    Special handling for 'Characters' as it involves 'Creatures' table."""
    conn = get_connection()
    if conn is None:
        return False
    cursor = conn.cursor()
    try:
        conn.start_transaction() # Start transaction for multi-table update

        if TARGET_TABLE_NAME == "Characters":
            # Update creature_name in Creatures table
            creature_name = data.get("creature_name")
            if creature_name:
                cursor.execute("UPDATE Creatures SET creature_name = %s WHERE creature_id = %s", (creature_name, pk_val))
            
            # Update gold in Characters table
            gold = data.get("gold")
            if gold is not None:
                cursor.execute(f"UPDATE {TARGET_TABLE_NAME} SET gold = %s WHERE character_id = %s", (gold, pk_val))
            
            conn.commit()
            st.success(f"Character (ID: {pk_val}) updated successfully!")
        else:
            # Generic update for other tables
            set_clause = ', '.join([f"{col}=%s" for col in data.keys()])
            pk_col = "id" # Assuming 'id' as primary key for other tables
            query = f"UPDATE {TARGET_TABLE_NAME} SET {set_clause} WHERE {pk_col} = %s"
            cursor.execute(query, tuple(data.values()) + (pk_val,))
            conn.commit()
            if cursor.rowcount > 0:
                st.success(f"Record (ID: {pk_val}) in {TARGET_TABLE_NAME} updated successfully!")
            else:
                st.warning(f"No record found with ID {pk_val} to update in {TARGET_TABLE_NAME}.")
        return True
    except Error as e:
        st.error(f"Error updating data in {TARGET_TABLE_NAME}: {e}")
        conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

def delete_row_generic(pk_val):
    """Deletes a row from the TARGET_TABLE_NAME based on its primary key.
    Special handling for 'Characters' due to foreign key constraints."""
    conn = get_connection()
    if conn is None:
        return False
    cursor = conn.cursor()
    try:
        conn.start_transaction() # Start transaction for multi-table deletion

        if TARGET_TABLE_NAME == "Characters":
            # Delete from Character_Classes, Character_Spells, Character_Combats, Inventory first
            cursor.execute("DELETE FROM Character_Classes WHERE character_id = %s", (pk_val,))
            cursor.execute("DELETE FROM Character_Spells WHERE character_id = %s", (pk_val,))
            cursor.execute("DELETE FROM Character_Combats WHERE creature_id = %s", (pk_val,)) # creature_id in Character_Combats
            cursor.execute("DELETE FROM Inventory WHERE creature_id = %s", (pk_val,)) # creature_id in Inventory

            # Then delete from Characters table
            cursor.execute(f"DELETE FROM {TARGET_TABLE_NAME} WHERE character_id = %s", (pk_val,))
            
            # Finally, delete from Creatures table
            cursor.execute("DELETE FROM Creatures WHERE creature_id = %s", (pk_val,))
            
            conn.commit()
            st.success(f"Character (ID: {pk_val}) and associated data deleted successfully!")
        else:
            # Generic delete for other tables
            pk_col = "id" # Assuming 'id' as primary key for other tables
            cursor.execute(f"DELETE FROM {TARGET_TABLE_NAME} WHERE {pk_col} = %s", (pk_val,))
            conn.commit()
            if cursor.rowcount > 0:
                st.success(f"Record (ID: {pk_val}) deleted from {TARGET_TABLE_NAME} successfully!")
            else:
                st.warning(f"No record found with ID {pk_val} to delete from {TARGET_TABLE_NAME}.")
        return True
    except Error as e:
        st.error(f"Error deleting data from {TARGET_TABLE_NAME}: {e}")
        conn.rollback()
        return False
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# --- Transaction: Transfer Gold Between Characters ---

def transfer_gold(from_id, to_id, amount): # Adapted from transfer_age
    """
    Transfers gold between two characters as a single transaction.
    Ensures either both gold is deducted and added, or neither.
    """
    conn = get_connection()
    if conn is None:
        return False, "Database connection failed."

    cursor = conn.cursor()
    try:
        conn.start_transaction()

        # 1. Get current gold for both characters
        cursor.execute(f"SELECT gold FROM {TARGET_TABLE_NAME} WHERE character_id = %s FOR UPDATE", (from_id,))
        from_gold_data = cursor.fetchone()
        cursor.execute(f"SELECT gold FROM {TARGET_TABLE_NAME} WHERE character_id = %s FOR UPDATE", (to_id,))
        to_gold_data = cursor.fetchone()

        if from_gold_data is None or to_gold_data is None:
            raise ValueError("One of the selected characters does not exist.")

        from_gold = from_gold_data[0]
        to_gold = to_gold_data[0]

        if from_gold < amount:
            raise ValueError("Insufficient gold to transfer.")

        # 2. Deduct gold from sender
        cursor.execute(f"UPDATE {TARGET_TABLE_NAME} SET gold = gold - %s WHERE character_id = %s", (amount, from_id))
        
        # 3. Add gold to recipient
        cursor.execute(f"UPDATE {TARGET_TABLE_NAME} SET gold = gold + %s WHERE character_id = %s", (amount, to_id))
        
        conn.commit()
        return True, "Gold transfer successful!"
    except Exception as e:
        conn.rollback()
        return False, f"Gold transfer failed: {e}"
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()


# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title(f"D&D Character Management App")
st.markdown(f"*(Generic CRUD operations for the **'{TARGET_TABLE_NAME}'** table)*")

# Create tabs for different functionalities
tab1, tab2, tab3, tab4, tab5 = st.tabs(["View Characters", "Add New Character", "Update Character", "Delete Character", "Transfer Gold (Transaction)"])

# --- Tab 1: View Records (Generic) ---
with tab1:
    st.header(f"All {TARGET_TABLE_NAME} Records")
    rows = fetch_all_generic()
    if rows:
        rows_df = pd.DataFrame(rows)
        st.dataframe(rows_df, use_container_width=True)
    else:
        st.info(f"No records found in the '{TARGET_TABLE_NAME}' table. Please add some characters.")

# --- Tab 2: Add New Record (Generic) ---
with tab2:
    st.header(f"Add New Character to '{TARGET_TABLE_NAME}'")
    with st.form("add_form"):
        new_data = {}
        for col_name, col_type in TARGET_COLUMNS.items():
            if col_name == "creature_name":
                new_data[col_name] = st.text_input("Character Name")
            elif col_name == "gold":
                new_data[col_name] = st.number_input("Starting Gold", min_value=0, value=100, step=1)
            else: # Fallback for any other type, though we only expect name and gold here
                new_data[col_name] = st.text_input(f"{col_name.replace('_', ' ').title()}")

        submitted = st.form_submit_button("Add Character")
        if submitted:
            if "creature_name" in new_data and not new_data["creature_name"]:
                st.error("Character Name cannot be empty.")
            else:
                insert_row_generic(new_data)
                st.rerun() # Refresh data after adding

# --- Tab 3: Update Record (Generic) ---
with tab3:
    st.header(f"Update Existing Character in '{TARGET_TABLE_NAME}'")
    rows_for_select = fetch_all_generic()
    
    # Create options for selectbox: "Character Name (ID: X)"
    row_options = {}
    for row in rows_for_select:
        display_name = row.get("creature_name", f"ID: {row['id']}") # Use creature_name if available, else ID
        row_options[f"{display_name} (ID: {row['id']})"] = row['id']

    selected_pk_name_display = st.selectbox(f"Select Character to Update",
                                            options=list(row_options.keys()),
                                            key="update_select",
                                            index=0 if row_options else None)

    selected_pk_val = row_options.get(selected_pk_name_display)
    current_record_details = None
    if selected_pk_val:
        current_record_details = next((row for row in rows_for_select if row['id'] == selected_pk_val), None)

    if current_record_details:
        with st.form("update_form"):
            updated_data = {}
            for col_name, col_type in TARGET_COLUMNS.items():
                current_value = current_record_details.get(col_name)
                if col_name == "creature_name":
                    updated_data[col_name] = st.text_input("Character Name", value=str(current_value if current_value is not None else ""), key=f"update_{col_name}")
                elif col_name == "gold":
                    updated_data[col_name] = st.number_input("Gold", min_value=0, value=int(current_value if current_value is not None else 0), step=1, key=f"update_{col_name}")
                else:
                    updated_data[col_name] = st.text_input(f"{col_name.replace('_', ' ').title()}", value=str(current_value if current_value is not None else ""), key=f"update_{col_name}")

            submitted_update = st.form_submit_button("Update Character")
            if submitted_update:
                if "creature_name" in updated_data and not updated_data["creature_name"]:
                    st.error("Character Name cannot be empty.")
                else:
                    update_row_generic(selected_pk_val, updated_data)
                    st.rerun() # Refresh data after update
    else:
        st.info(f"No characters available to update. Add some first!")


# --- Tab 4: Delete Record (Generic) ---
with tab4:
    st.header(f"Delete Character from '{TARGET_TABLE_NAME}'")
    rows_for_delete = fetch_all_generic()
    
    # Create options for selectbox: "Character Name (ID: X)"
    row_delete_options = {}
    for row in rows_for_delete:
        display_name = row.get("creature_name", f"ID: {row['id']}") # Use creature_name if available, else ID
        row_delete_options[f"{display_name} (ID: {row['id']})"] = row['id']

    selected_pk_to_delete_display = st.selectbox(f"Select Character to Delete",
                                                options=list(row_delete_options.keys()),
                                                key="delete_select",
                                                index=0 if row_delete_options else None)

    selected_pk_to_delete_val = row_delete_options.get(selected_pk_to_delete_display)

    if selected_pk_to_delete_val:
        st.warning(f"Are you sure you want to delete '{selected_pk_to_delete_display}' and all its associated data?")
        if st.button("Confirm Delete"): # Changed key to avoid conflict if any other button has "delete"
            delete_row_generic(selected_pk_to_delete_val)
            st.rerun() # Refresh data after deletion
    else:
        st.info(f"No characters available to delete. Add some first!")

# --- Tab 5: Transfer Gold (Transaction) ---
with tab5:
    st.subheader("Transfer Gold Between Characters (Transactional)")

    rows = fetch_all_generic() # Re-fetch to get latest gold values
    if not rows or len(rows) < 2:
        st.warning("Not enough characters to perform a gold transfer. Please add at least 2 characters.")
        # Do not st.stop() here as it prevents other tabs from rendering.
        # Instead, disable the transfer button and inputs.
        st.markdown("---") # Separator
        st.info("Add more characters to enable gold transfer.")
        # Disable inputs/button if not enough characters
        st.selectbox("From (Character)", ["N/A"], disabled=True, key="from_char_select_disabled")
        st.selectbox("To (Character)", ["N/A"], disabled=True, key="to_char_select_disabled")
        st.number_input("Amount of Gold to Transfer", min_value=1, step=1, disabled=True, key="transfer_amount_disabled")
        st.button("Transfer Gold", disabled=True, key="transfer_gold_disabled")
    else:
        # Create name-to-id and id-to-name/gold mappings
        name_id_map = {f"{row['creature_name']} (ID {row['id']})": row['id'] for row in rows}
        id_name_map = {row['id']: row['creature_name'] for row in rows}
        id_gold_map = {row['id']: row['gold'] for row in rows}

        from_name_display = st.selectbox("From (Character)", list(name_id_map.keys()), key="from_char_select")
        to_name_options_display = [n for n in name_id_map.keys() if n != from_name_display]

        if not to_name_options_display:
            st.warning("Please select a different 'From' character to enable 'To' selection.")
            st.selectbox("To (Character)", ["N/A"], disabled=True, key="to_char_select_disabled_2")
            st.number_input("Amount of Gold to Transfer", min_value=1, step=1, disabled=True, key="transfer_amount_disabled_2")
            st.button("Transfer Gold", disabled=True, key="transfer_gold_disabled_2")
        else:
            to_name_display = st.selectbox("To (Character)", to_name_options_display, key="to_char_select")

            from_id = name_id_map.get(from_name_display)
            to_id = name_id_map.get(to_name_display)

            if from_id and to_id: # Ensure both IDs are valid before displaying info
                st.markdown(f"**{id_name_map[from_id]}'s current gold:** {id_gold_map[from_id]} GP")
                st.markdown(f"**{id_name_map[to_id]}'s current gold:** {id_gold_map[to_id]} GP")

            amount = st.number_input(
                "Amount of Gold to Transfer",
                min_value=1,
                step=1,
                key="transfer_amount"
            )

            if st.button("Transfer Gold"):
                if from_id == to_id:
                    st.error("Cannot transfer gold to the same character!")
                elif from_id and to_id and amount:
                    success, msg = transfer_gold(from_id, to_id, amount)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun() # Refresh to show updated gold values
                else:
                    st.warning("Please select both characters and a valid amount.")

# --- End of Streamlit UI ---
