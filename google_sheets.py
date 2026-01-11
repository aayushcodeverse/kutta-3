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
            return None
        try:
            creds_dict = json.loads(self.credentials_json)
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"Connection Error: {e}")
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
                return sheet
        except Exception as e:
            print(f"Sheet Access Error: {e}")
            return None

    def validate_voting_id(self, voting_id):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return False
        cell = sheet.find(voting_id)
        if cell:
            row = sheet.row_values(cell.row)
            # Schema: VotingID | Class | Section | RollNo | Used
            return row[4].upper() == 'NO'
        return False

    def mark_voting_id_used(self, voting_id):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return
        try:
            cell = sheet.find(voting_id)
            if cell:
                # Column 5 is 'Used'
                sheet.update_cell(cell.row, 5, 'YES')
        except gspread.exceptions.CellNotFound:
            print(f"Voter ID {voting_id} not found in sheet.")

    def store_vote(self, voting_id, votes_dict):
        sheet = self._get_sheet('VOTES')
        if not sheet: return
        # Schema: VotingID | HeadBoy | HeadGirl | SportsCaptain | CulturalSecretary | Timestamp
        row = [
            voting_id,
            votes_dict.get('Head Boy', 'NOTA'),
            votes_dict.get('Head Girl', 'NOTA'),
            votes_dict.get('Sports Captain', 'NOTA'),
            votes_dict.get('Cultural Secretary', 'NOTA'),
            datetime.datetime.now().isoformat()
        ]
        sheet.append_row(row)

    def generate_voting_id(self):
        sheet = self._get_sheet('VOTERS')
        while True:
            new_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not sheet or not sheet.find(new_id):
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

    def get_all_voters(self):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return []
        records = sheet.get_all_records()
        return records

    def get_all_votes(self):
        sheet = self._get_sheet('VOTES')
        if not sheet: return []
        records = sheet.get_all_records()
        return records
