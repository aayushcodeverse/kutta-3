from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import random
import string
import datetime
from google_sheets import GoogleSheetsDB

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'school-election-secret-key')

# Initialize Google Sheets DB
db = GoogleSheetsDB()

ADMIN_PASSWORDS = ['Aayush@2011', 'Purvi@240111']

# Cache for Sheet data to improve performance
class SheetCache:
    def __init__(self):
        self.data = {}
        self.expiry = {}
        self.ttl = 30 # 30 seconds cache

    def get(self, key):
        if key in self.data and datetime.datetime.now() < self.expiry[key]:
            return self.data[key]
        return None

    def set(self, key, value):
        self.data[key] = value
        self.expiry[key] = datetime.datetime.now() + datetime.timedelta(seconds=self.ttl)

cache = SheetCache()

def get_posts_and_candidates():
    # Bypass cache for troubleshooting
    posts = db.get_all_posts()
    if not posts:
        posts = ['Head Boy', 'Head Girl', 'Sports Captain', 'Cultural Secretary']
    
    dynamic_candidates = db.get_candidates_by_post()
    
    candidates_map = {}
    for post in posts:
        # Normalize post name for comparison
        normalized_post = post.strip()
        candidates_list = []
        
        # Check all dynamic candidates for matches
        for p, clist in dynamic_candidates.items():
            if p.strip().lower() == normalized_post.lower():
                candidates_list.extend(clist)
        
        # Ensure 'NOTA' is present
        if not any(isinstance(c, dict) and c.get('name') == 'NOTA' for c in candidates_list):
            candidates_list.append({'name': 'NOTA', 'image': '', 'motto': ''})
            
        candidates_map[post] = candidates_list
            
    return posts, candidates_map

@app.route('/admin/posts/add', methods=['POST'])
def add_post():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    post_name = request.form.get('post_name')
    if post_name:
        db.add_post(post_name)
        cache.data.pop('posts_candidates', None) # Invalidate cache
    return redirect(url_for('admin_dashboard'))

@app.route('/')
def home():
    return render_template('index.html')

# --- APP 1: VOTER ID GENERATOR ---
@app.route('/voter-gen', methods=['GET', 'POST'])
def voter_gen():
    if request.method == 'POST':
        student_class = request.form.get('class')
        section = request.form.get('section')
        roll_no = request.form.get('roll_no')
        
        if student_class not in ['8', '9']:
            flash('Only Class 8 & 9 are eligible.')
            return redirect(url_for('voter_gen'))
            
        voter_id = db.generate_voting_id()
        db.add_voter({
            'VotingID': voter_id,
            'Class': student_class,
            'Section': section,
            'RollNo': roll_no
        })
        return render_template('voter_gen/success.html', voter_id=voter_id)
    return render_template('voter_gen/index.html')

@app.route('/verify-voter', methods=['GET', 'POST'])
def verify_voter():
    return vote()

# --- APP 2: DIGITAL VOTING SYSTEM ---
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if request.method == 'POST':
        voter_id = request.form.get('voter_id')
        # Validate 4-digit numeric constraint
        if voter_id and voter_id.isdigit() and len(voter_id) == 4:
            if db.validate_voting_id(voter_id):
                session['voter_id'] = voter_id
                session['current_votes'] = {}
                return redirect(url_for('voting_flow', step=1))
            else:
                flash('Invalid or already used Voting ID.')
        else:
            flash('Voter ID must be a 4-digit number.')
        return redirect(url_for('verify_voter'))
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
    
    posts, candidates_map = get_posts_and_candidates()
    
    if step > len(posts):
        return redirect(url_for('confirm_votes'))
    
    current_post = posts[step-1]
    if request.method == 'POST':
        selection = request.form.get('selection')
        if not selection:
            flash('Please select an option.')
            return redirect(url_for('voting_flow', step=step))
        
        votes = session.get('current_votes', {})
        votes[current_post] = selection
        session['current_votes'] = votes
        return redirect(url_for('voting_flow', step=step+1))
        
    return render_template('voting_system/step.html', 
                          post=current_post, 
                          candidates=candidates_map[current_post], 
                          step=step, 
                          total=len(posts))

@app.route('/confirm-votes', methods=['GET', 'POST'])
def confirm_votes():
    if 'voter_id' not in session or 'current_votes' not in session:
        return redirect(url_for('vote'))
        
    if request.method == 'POST':
        voter_id = session.pop('voter_id')
        votes = session.pop('current_votes')
        
        # Save votes and mark used in Sheets
        db.store_vote(voter_id, votes)
        db.mark_voting_id_used(voter_id)
        
        return render_template('voting_system/thanks.html')
        
    return render_template('voting_system/confirm.html', votes=session['current_votes'])

# --- ADMIN PANEL ---
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') in ADMIN_PASSWORDS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Invalid password')
    return render_template('admin/login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    posts, candidates_map = get_posts_and_candidates()
    return render_template('admin/dashboard.html', 
                          voters=db.get_all_voters(), 
                          votes=db.get_all_votes(),
                          candidates=candidates_map,
                          posts=posts)

@app.route('/admin/candidates/add', methods=['POST'])
def add_candidate():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    post = request.form.get('post')
    name = request.form.get('name')
    image_url = request.form.get('image_url', '')
    motto = request.form.get('motto', '')
    if post and name:
        db.add_candidate(post, name, image_url, motto)
        cache.data.pop('posts_candidates', None) # Invalidate cache
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/candidates/delete/<candidate_id>')
def delete_candidate(candidate_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    db.delete_candidate(candidate_id)
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    app.run(host='0.0.0.0', port=5000)
