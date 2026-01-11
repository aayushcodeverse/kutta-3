from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import random
import string
import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'school-election-secret-key')

# Mock Database (to be replaced with Google Sheets API)
VOTERS_SHEET = [] # Schema: VotingID, Class, Section, RollNo, Used
VOTES_SHEET = []  # Schema: VotingID, HeadBoy, HeadGirl, SportsCaptain, CulturalSecretary, Timestamp

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

def generate_voter_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@app.route('/')
def home():
    return render_template('index.html')

# --- APP 1: VOTER ID GENERATOR ---
@app.route('/voter-gen', methods=['GET', 'POST'])
def voter_gen():
    if request.method == 'POST':
        name = request.form.get('name')
        student_class = request.form.get('class')
        section = request.form.get('section')
        roll_no = request.form.get('roll_no')
        
        if student_class not in ['8', '9']:
            flash('Only Class 8 & 9 are eligible.')
            return redirect(url_for('voter_gen'))
            
        voter_id = generate_voter_id()
        VOTERS_SHEET.append({
            'VotingID': voter_id,
            'Class': student_class,
            'Section': section,
            'RollNo': roll_no,
            'Used': 'NO'
        })
        return render_template('voter_gen/success.html', voter_id=voter_id)
    return render_template('voter_gen/index.html')

# --- APP 2: DIGITAL VOTING SYSTEM ---
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if request.method == 'POST':
        voter_id = request.form.get('voter_id')
        voter = next((v for v in VOTERS_SHEET if v['VotingID'] == voter_id and v['Used'] == 'NO'), None)
        
        if not voter:
            flash('Invalid or already used Voting ID.')
            return redirect(url_for('vote'))
        
        session['voter_id'] = voter_id
        session['current_votes'] = {}
        return redirect(url_for('voting_flow', step=1))
    return render_template('voting_system/index.html')

POSTS = ['Head Boy', 'Head Girl', 'Sports Captain', 'Cultural Secretary']
CANDIDATES = {
    'Head Boy': ['Candidate A', 'Candidate B', 'NOTA'],
    'Head Girl': ['Candidate C', 'Candidate D', 'NOTA'],
    'Sports Captain': ['Candidate E', 'Candidate F', 'NOTA'],
    'Cultural Secretary': ['Candidate G', 'Candidate H', 'NOTA']
}

@app.route('/voting-flow/<int:step>', methods=['GET', 'POST'])
def voting_flow(step):
    if 'voter_id' not in session:
        return redirect(url_for('vote'))
    
    if step > len(POSTS):
        return redirect(url_for('confirm_votes'))
    
    current_post = POSTS[step-1]
    if request.method == 'POST':
        selection = request.form.get('selection')
        if not selection:
            flash('Please select an option.')
            return redirect(url_for('voting_flow', step=step))
        
        votes = session.get('current_votes', {})
        votes[current_post] = selection
        session['current_votes'] = votes
        return redirect(url_for('voting_flow', step=step+1))
        
    return render_template('voting_system/step.html', post=current_post, candidates=CANDIDATES[current_post], step=step, total=len(POSTS))

@app.route('/confirm-votes', methods=['GET', 'POST'])
def confirm_votes():
    if 'voter_id' not in session or 'current_votes' not in session:
        return redirect(url_for('vote'))
        
    if request.method == 'POST':
        voter_id = session.pop('voter_id')
        votes = session.pop('current_votes')
        
        # Mark voter as used
        for v in VOTERS_SHEET:
            if v['VotingID'] == voter_id:
                v['Used'] = 'YES'
                break
        
        # Save votes
        votes['VotingID'] = voter_id
        votes['Timestamp'] = datetime.datetime.now().isoformat()
        VOTES_SHEET.append(votes)
        
        return render_template('voting_system/thanks.html')
        
    return render_template('voting_system/confirm.html', votes=session['current_votes'])

# --- ADMIN PANEL ---
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid password')
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    return render_template('admin/dashboard.html', voters=VOTERS_SHEET, votes=VOTES_SHEET)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
