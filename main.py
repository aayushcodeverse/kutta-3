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
        found_candidates = []
        for p, clist in dynamic_candidates.items():
            if p.strip().lower() == normalized_post.lower():
                found_candidates.extend(clist)
        
        candidates_list.extend(found_candidates)
        
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
            details = db.get_voter_details(voter_id)
            if details:
                if not details['used']:
                    session['pending_voter_id'] = voter_id
                    return render_template('voting_system/id_details.html', voter_id=voter_id, details=details)
                else:
                    flash('This Voting ID has already been used.')
            else:
                flash('Invalid Voting ID. Please check and try again.')
        else:
            flash('Voter ID must be a 4-digit number.')
        return redirect(url_for('vote'))
    return render_template('voting_system/index.html')

@app.route('/start-ballot', methods=['POST'])
def start_ballot():
    if 'pending_voter_id' in session:
        voter_id = session.pop('pending_voter_id')
        session['voter_id'] = voter_id
        session['current_votes'] = {}
        return redirect(url_for('voting_flow', step=1))
    return redirect(url_for('vote'))

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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_otp_email(receiver_email, otp):
    sender_email = os.environ.get('GMAIL_USER')
    password = os.environ.get('GMAIL_APP_PASSWORD')
    
    if not sender_email or not password:
        print("DEBUG: Email credentials missing")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = f"Election System <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = "Your Admin Login OTP"
    
    body = f"""
    Hello Admin,
    
    Your OTP for the Election System login is: {otp}
    
    This OTP will expire shortly. Please do not share this with anyone.
    
    Regards,
    Little Scholars Academy
    """
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"DEBUG: Failed to send email: {e}")
        return False

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        otp = request.form.get('otp')
        
        if not session.get('pending_admin_login'):
            if password in ADMIN_PASSWORDS:
                # Generate and "send" OTP
                generated_otp = ''.join(random.choices(string.digits, k=6))
                session['admin_otp'] = generated_otp
                session['pending_admin_login'] = True
                
                admin_email = os.environ.get('ADMIN_EMAIL')
                email_sent = False
                if admin_email:
                    email_sent = send_otp_email(admin_email, generated_otp)
                
                print(f"\n[ADMIN OTP] The OTP for admin login is: {generated_otp}\n")
                
                if email_sent:
                    flash(f'OTP sent to {admin_email}. Please enter it to continue.')
                else:
                    flash('OTP generated. (Email delivery failed, check console for development OTP)')
                
                return render_template('admin/login.html', otp_sent=True)
            flash('Invalid password')
        else:
            if otp == session.get('admin_otp'):
                session.pop('admin_otp', None)
                session.pop('pending_admin_login', None)
                session['admin_logged_in'] = True
                return redirect(url_for('admin_dashboard'))
            flash('Invalid OTP')
            return render_template('admin/login.html', otp_sent=True)
            
    return render_template('admin/login.html', otp_sent=False)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    posts, candidates_map = get_posts_and_candidates()
    # Fetch all records including candidates for ID matching
    all_candidates_raw = db.get_all_records_safe('CANDIDATES')
    
    return render_template('admin/dashboard.html', 
                          voters=db.get_all_voters(), 
                          votes=db.get_all_votes(),
                          candidates=candidates_map,
                          all_candidates_raw=all_candidates_raw,
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
    cache.data.pop('posts_candidates', None) # Invalidate cache
    return redirect(url_for('admin_dashboard'))

@app.route('/results')
def public_results():
    posts, candidates_map = get_posts_and_candidates()
    all_votes = db.get_all_votes()
    all_voters = db.get_all_voters()
    
    total_voters = len(all_voters)
    votes_cast = len(all_votes)
    votes_remaining = total_voters - votes_cast
    
    results = {}
    for post in posts:
        post_results = {}
        # Count votes for each candidate
        for vote_record in all_votes:
            selection = vote_record.get(post)
            if selection:
                post_results[selection] = post_results.get(selection, 0) + 1
        
        # Add candidates with 0 votes for completeness
        for candidate in candidates_map.get(post, []):
            name = candidate['name']
            if name not in post_results:
                post_results[name] = 0
                
        results[post] = post_results

    return render_template('results.html', 
                          results=results, 
                          total_voters=total_voters,
                          votes_cast=votes_cast,
                          votes_remaining=votes_remaining,
                          candidates_map=candidates_map,
                          now=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    app.run(host='0.0.0.0', port=5000)
