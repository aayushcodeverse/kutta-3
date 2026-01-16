import os
import json
import random
import string
from google_sheets import GoogleSheetsDB

def populate():
    db = GoogleSheetsDB()
    sheet = db._get_sheet('VOTERS')
    if not sheet:
        print("Error: Could not access VOTERS sheet")
        return

    # Fetch existing voters to prevent duplicates
    existing_records = db.get_all_voters()
    existing_keys = set()
    for r in existing_records:
        key = f"{r.get('Class')}_{r.get('Section')}_{r.get('RollNo')}"
        existing_keys.add(key)

    classes = ['8', '9']
    sections = ['A', 'B', 'C', 'D']
    roll_limit = 62

    total_attempted = 0
    successfully_inserted = 0
    duplicates_skipped = 0
    
    new_rows = []
    
    # Existing logic for VotingID generation needs to check against what we're adding too
    generated_ids = set(r.get('VotingID') for r in existing_records)

    for cls in classes:
        for sec in sections:
            for roll in range(1, roll_limit + 1):
                total_attempted += 1
                key = f"{cls}_{sec}_{roll}"
                
                if key in existing_keys:
                    duplicates_skipped += 1
                    continue
                
                # Generate unique 4-digit ID
                while True:
                    vid = ''.join(random.choices(string.digits, k=4))
                    if vid not in generated_ids:
                        generated_ids.add(vid)
                        break
                
                # Column Order: VotingID, Class, Section, RollNo, Used
                # User wants Class, Section, Roll Number, Student Name, Voting ID, Voting Status
                # Wait, the rule says "in the SAME COLUMN ORDER already used by the project"
                # google_sheets.py says: ['VotingID', 'Class', 'Section', 'RollNo', 'Used']
                # The user description (point 4) says: Class, Section, Roll Number, Student Name, Voting ID, Voting Status
                # But rule 4 also says "in the SAME COLUMN ORDER already used by the project".
                # And "DO NOT invent a new schema. Match the EXACT column structure already used in the Google Sheet."
                # My google_sheets.py code uses: VotingID, Class, Section, RollNo, Used
                
                # Let's check the existing code again:
                # db.add_voter uses: [voter_data['VotingID'], voter_data['Class'], voter_data['Section'], voter_data['RollNo'], 'NO']
                
                new_rows.append([vid, cls, sec, str(roll), 'NO'])
                successfully_inserted += 1

    if new_rows:
        # Batch insert for efficiency
        sheet.append_rows(new_rows)

    print(f"Total students attempted: {total_attempted}")
    print(f"Total students successfully inserted: {successfully_inserted}")
    print(f"Total duplicates skipped: {duplicates_skipped}")

if __name__ == '__main__':
    populate()
