import gspread
import os
import json
import random
import string
import datetime
from google.oauth2.service_account import Credentials

class GoogleSheetsDB:
    def __init__(self):
        self.sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        self.credentials_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_JSON')
        self.client = self._connect()

    def _connect(self):
        if not self.credentials_json or not self.sheet_id:
            print("Google Sheets: Configuration missing (Credentials or Sheet ID)")
            return None
        try:
            creds_dict = json.loads(self.credentials_json)
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
            print("Google Sheets: Initialized successfully ✅")
            return client
        except Exception as e:
            print(f"Google Sheets: Initialization failed ❌ - {e}")
            return None

    def _get_sheet(self, name):
        if not self.client or not self.sheet_id: return None
        try:
            spreadsheet = self.client.open_by_key(self.sheet_id)
            try:
                return spreadsheet.worksheet(name)
            except gspread.exceptions.WorksheetNotFound:
                # Create sheet and add headers
                sheet = spreadsheet.add_worksheet(title=name, rows="100", cols="20")
                if name == 'VOTERS':
                    sheet.append_row(['VotingID', 'Class', 'Section', 'RollNo', 'Used'])
                elif name == 'VOTES':
                    sheet.append_row(['VotingID', 'Head Boy', 'Head Girl', 'Sports Captain', 'Cultural Secretary', 'Timestamp'])
                elif name == 'CANDIDATES':
                    sheet.append_row(['Post', 'CandidateID', 'Name', 'ImageURL', 'Motto', 'Active'])
                elif name == 'POSTS':
                    sheet.append_row(['PostName', 'Active'])
                return sheet
        except Exception as e:
            print(f"Sheet Access Error: {e}")
            return None

    def add_post(self, post_name):
        sheet = self._get_sheet('POSTS')
        if not sheet: return
        sheet.append_row([post_name, 'YES'])

    def get_all_records_safe(self, name):
        sheet = self._get_sheet(name)
        if not sheet: return []
        try:
            values = sheet.get_all_values()
            if not values or len(values) < 1: return []
            headers = [h.strip() for h in values[0]]
            records = []
            for row in values[1:]:
                record = {}
                for i, header in enumerate(headers):
                    if header:
                        record[header] = row[i] if i < len(row) else ''
                records.append(record)
            return records
        except Exception as e:
            print(f"Error reading {name}: {e}")
            return []

    def get_all_posts(self):
        records = self.get_all_records_safe('POSTS')
        return [r['PostName'] for r in records if r.get('Active', '').upper() == 'YES']

    def validate_voting_id(self, voting_id):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return False
        try:
            cell = sheet.find(voting_id)
            if cell:
                row = sheet.row_values(cell.row)
                return row[4].upper() == 'NO'
        except:
            pass
        return False

    def store_vote(self, voting_id, votes_dict):
        sheet = self._get_sheet('VOTES')
        if not sheet: return
        # Schema: VotingID | [Dynamic Posts] | Timestamp
        posts = self.get_all_posts()
        row = [voting_id]
        for post in posts:
            row.append(votes_dict.get(post, 'NOTA'))
        row.append(datetime.datetime.now().isoformat())
        sheet.append_row(row)

    def generate_voting_id(self):
        sheet = self._get_sheet('VOTERS')
        while True:
            new_id = ''.join(random.choices(string.digits, k=4))
            # Safe check
            try:
                if not sheet or not sheet.find(new_id):
                    return new_id
            except:
                return new_id

    def add_voter(self, voter_data):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return
        # Schema: VotingID | Class | Section | RollNo | Used
        row = [
            voter_data['VotingID'],
            voter_data['Class'],
            voter_data['Section'],
            voter_data['RollNo'],
            'NO'
        ]
        sheet.append_row(row)

    def delete_candidate(self, candidate_id):
        sheet = self._get_sheet('CANDIDATES')
        if not sheet: return
        try:
            cell = sheet.find(candidate_id)
            if cell:
                sheet.delete_rows(cell.row)
        except Exception as e:
            print(f"Error deleting candidate: {e}")
