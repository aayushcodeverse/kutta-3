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
                    sheet.append_row(['VotingID', 'Timestamp']) # Will append posts dynamically
                elif name == 'CANDIDATES':
                    sheet.append_row(['Post', 'CandidateID', 'Name', 'ImageURL', 'Motto', 'Active'])
                elif name == 'POSTS':
                    sheet.append_row(['PostName', 'Active'])
                return sheet
        except Exception as e:
            print(f"Sheet Access Error: {e}")
            return None

    def get_all_records_safe(self, name):
        sheet = self._get_sheet(name)
        if not sheet: return []
        try:
            values = sheet.get_all_values()
            if not values or len(values) < 1: return []
            
            # Map headers to column indices, ignoring empty headers
            header_row = values[0]
            header_map = {}
            for i, h in enumerate(header_row):
                clean_h = h.strip()
                if clean_h:
                    header_map[clean_h] = i
            
            records = []
            for row in values[1:]:
                record = {}
                for h, idx in header_map.items():
                    record[h] = row[idx] if idx < len(row) else ''
                # Only add if record has at least some data
                if any(str(v).strip() for v in record.values()):
                    records.append(record)
            return records
        except Exception as e:
            print(f"Error reading {name}: {e}")
            return []

    def get_voter_by_details(self, class_val, section, roll_no):
        records = self.get_all_voters()
        for r in records:
            if str(r.get('Class')) == str(class_val) and \
               str(r.get('Section')).upper() == str(section).upper() and \
               str(r.get('RollNo')) == str(roll_no):
                return {
                    'voter_id': r.get('VotingID'),
                    'used': str(r.get('Used', 'NO')).upper() == 'YES'
                }
        return None

    def add_post(self, post_name):
        sheet = self._get_sheet('POSTS')
        if not sheet: return
        sheet.append_row([post_name, 'YES'])

    def get_all_posts(self):
        records = self.get_all_records_safe('POSTS')
        posts = [r['PostName'] for r in records if str(r.get('Active', '')).upper() in ['YES', '']]
        if not posts:
            posts = ['PRIME MINISTER', 'CULTURAL MINISTER', 'SPORTS MINISTER', 'FINANCE MINISTER', 'INFORMATION MINISTER', 'DISCIPLINE MINISTER']
        return posts

    def get_voter_details(self, voting_id):
        records = self.get_all_voters()
        for r in records:
            if str(r.get('VotingID')) == str(voting_id):
                return {
                    'class': r.get('Class'),
                    'section': r.get('Section'),
                    'roll_no': r.get('RollNo'),
                    'used': str(r.get('Used', 'NO')).upper() == 'YES'
                }
        return None

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

    def mark_voting_id_used(self, voting_id):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return False
        try:
            cell = sheet.find(voting_id)
            if cell:
                sheet.update_cell(cell.row, 5, 'YES')
                return True
        except Exception as e:
            print(f"Error marking ID used: {e}")
        return False

    def store_vote(self, voting_id, votes_dict):
        sheet = self._get_sheet('VOTES')
        if not sheet: return False
        try:
            posts = self.get_all_posts()
            row = [voting_id]
            for post in posts:
                row.append(votes_dict.get(post, 'NOTA'))
            row.append(datetime.datetime.now().isoformat())
            sheet.append_row(row)
            return True
        except Exception as e:
            print(f"Error storing vote: {e}")
            return False

    def generate_voting_id(self):
        sheet = self._get_sheet('VOTERS')
        while True:
            new_id = ''.join(random.choices(string.digits, k=4))
            try:
                if not sheet or not sheet.find(new_id):
                    return new_id
            except:
                return new_id

    def add_voter(self, voter_data):
        sheet = self._get_sheet('VOTERS')
        if not sheet: return
        
        # Check if voter already exists by VotingID
        try:
            if sheet.find(voter_data['VotingID']):
                return
        except:
            pass

        row = [voter_data['VotingID'], voter_data['Class'], voter_data['Section'], voter_data['RollNo'], 'NO']
        sheet.append_row(row)

    def get_all_voters(self):
        return self.get_all_records_safe('VOTERS')

    def get_all_votes(self):
        return self.get_all_records_safe('VOTES')

    def get_candidates_by_post(self):
        records = self.get_all_records_safe('CANDIDATES')
        candidates = {}
        for r in records:
            post = r.get('Post')
            if not post: continue
            
            name = r.get('Name')
            image_url = r.get('ImageURL', '')
            motto = r.get('Motto', '')
            active_val = str(r.get('Active', '')).strip()

            # Fix for misaligned headers: if Active contains a URL, it's likely the ImageURL
            if not image_url and 'Active' in r and r['Active'].startswith('http'):
                image_url = r['Active']
            
            if post not in candidates:
                candidates[post] = []
            
            # Map role based on active_val (vote value)
            role = ''
            if active_val == '10':
                role = 'MAIN MINISTER'
            elif active_val == '9':
                role = 'DY MINISTER'
            
            candidates[post].append({
                'name': name,
                'image': image_url,
                'motto': motto,
                'active_raw': active_val,
                'role': role
            })
        return candidates

    def add_candidate(self, post, name, image_url='', motto='', active='10'):
        sheet = self._get_sheet('CANDIDATES')
        if not sheet: return
        
        # Safe insert: Only add if missing
        existing = self.get_candidates_by_post()
        clist = existing.get(post, [])
        if any(c['name'] == name for c in clist):
            return

        candidate_id = ''.join(random.choices(string.digits, k=4))
        sheet.append_row([post, candidate_id, name, image_url, motto, active])

    def delete_candidate(self, candidate_id):
        sheet = self._get_sheet('CANDIDATES')
        if not sheet: return
        try:
            cell = sheet.find(candidate_id)
            if cell:
                sheet.delete_rows(cell.row)
        except Exception as e:
            print(f"Error deleting candidate: {e}")
