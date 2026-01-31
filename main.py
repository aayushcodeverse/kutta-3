import json
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

ADMIN_PASSWORDS = ['MANOJ@123']

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
        self.expiry[key] = datetime.datetime.now() + datetime.timedelta(minutes=30)  # Increase to 30 mins

cache = SheetCache()

def get_posts_and_candidates():
    # Use cache for performance
    cached_data = cache.get('posts_candidates')
    if cached_data:
        return cached_data['posts'], cached_data['candidates']
        
    posts = db.get_all_posts()
    dynamic_candidates = db.get_candidates_by_post()
    
    candidates_map = {}
    for post in posts:
        clist = dynamic_candidates.get(post, [])
        # Auto-assign role based on Active (vote value)
        processed_list = []
        for c in clist:
            active_val = str(c.get('active_raw', '')).strip()
            role = ''
            if active_val == '10':
                role = 'MAIN MINISTER'
            elif active_val == '9':
                role = 'DY MINISTER'
            c['role'] = role
            processed_list.append(c)
        candidates_map[post] = processed_list
    
    # Store in cache
    cache.set('posts_candidates', {'posts': posts, 'candidates': candidates_map})
    return posts, candidates_map

@app.route('/admin/posts/add', methods=['POST'])
def add_post():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    post_name = request.form.get('post_name')
    if post_name:
        db.add_post(post_name)
        cache.data.pop('posts_candidates', None) # Invalidate cache
        flash(f'Post "{post_name}" created successfully.', 'success')
    else:
        flash('Post name is required.', 'error')
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
            flash('Only Class 8 & 9 are eligible.', 'error')
            return redirect(url_for('voter_gen'))
            
        voter_id = db.generate_voting_id()
        if db.add_voter({
            'VotingID': voter_id,
            'Class': student_class,
            'Section': section,
            'RollNo': roll_no
        }):
            flash('Voter Identity provisioned successfully.', 'success')
            return render_template('voter_gen/success.html', voter_id=voter_id)
        else:
            flash('Critical: Database synchronization failed.', 'error')
            return redirect(url_for('voter_gen'))
    return render_template('voter_gen/index.html')

@app.route('/verify-voter', methods=['GET', 'POST'])
def verify_voter():
    return vote()

# --- APP 2: DIGITAL VOTING SYSTEM ---
@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if request.method == 'POST':
        voter_id = request.form.get('voter_id')
        if voter_id and voter_id.isdigit() and len(voter_id) == 4:
            details = db.get_voter_details(voter_id)
            if details:
                if not details['used']:
                    session['pending_voter_id'] = voter_id
                    flash('Identity verified. Proceed to ballot.', 'success')
                    return render_template('voting_system/id_details.html', voter_id=voter_id, details=details)
                else:
                    flash('Security Violation: ID already utilized.', 'error')
            else:
                flash('Identification Error: 4-digit ID not found.', 'error')
        else:
            flash('Input Error: Voter ID must be exactly 4 digits.', 'error')
        return redirect(url_for('vote'))
    return render_template('voting_system/index.html')

@app.route('/start-ballot', methods=['POST'])
def start_ballot():
    if 'pending_voter_id' in session:
        voter_id = session.pop('pending_voter_id')
        details = db.get_voter_details(voter_id)
        session['voter_id'] = voter_id
        session['voter_details'] = details
        session['session_timestamp'] = datetime.datetime.now().strftime('%Y%m%d_%HH%MM%SS')
        session['current_votes'] = {}
        flash('Voting session initialized.', 'success')
        return redirect(url_for('voting_flow', step=1))
    flash('Session timeout. Please re-verify ID.', 'error')
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
        flash('Unauthorized Access: Please verify ID first.', 'error')
        return redirect(url_for('vote'))
    
    posts, candidates_map = get_posts_and_candidates()
    
    if step > len(posts):
        return redirect(url_for('confirm_votes'))
    
    current_post = posts[step-1]
    if request.method == 'POST':
        selection = request.form.get('selection')
        if not selection:
            flash('Please select a candidate or NOTA.', 'error')
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
        voter_id = session.get('voter_id')
        votes = session.get('current_votes')
        
        if not voter_id or not votes:
            print(f"DEBUG: Session lost. voter_id: {voter_id}, votes: {votes is not None}")
            flash('Session timeout. Please try again.', 'error')
            return redirect(url_for('vote'))

        # Save votes and mark used in Sheets
        try:
            stored = db.store_vote(voter_id, votes)
            marked = db.mark_voting_id_used(voter_id)
            
            if stored or marked: # Even if one succeeds, we consider it progress
                session.pop('voter_id', None)
                session.pop('current_votes', None)
                flash('Vote recorded successfully.', 'success')
                return render_template('voting_system/thanks.html')
            else:
                print(f"DEBUG: Vote storage failed. Stored: {stored}, Marked: {marked}")
                flash('Transmission failure. Please contact supervisor.', 'error')
        except Exception as e:
            print(f"DEBUG: Critical error in confirm_votes: {e}")
            flash('System Error. Please notify technical staff.', 'error')
            
        return redirect(url_for('vote'))
        
    return render_template('voting_system/confirm.html', votes=session['current_votes'])

# --- ADMIN PANEL ---
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from twilio.rest import Client

def send_otp_whatsapp(receiver_phone, otp):
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    from_whatsapp_number = os.environ.get('TWILIO_WHATSAPP_NUMBER')
    content_sid = 'HX229f5a04fd0510ce1b071852155d3e75'  # As provided by user
    
    if not all([account_sid, auth_token, from_whatsapp_number]):
        print("DEBUG: Missing Twilio credentials")
        return False
        
    try:
        client = Client(account_sid, auth_token)
        
        # Ensure numbers are strings and handled safely
        from_whatsapp_number = str(from_whatsapp_number)
        receiver_phone = str(receiver_phone)
        
        # Ensure numbers are in whatsapp: format
        if not from_whatsapp_number.startswith('whatsapp:'):
            from_whatsapp_number = f'whatsapp:{from_whatsapp_number}'
        
        if not receiver_phone.startswith('whatsapp:'):
            receiver_phone = f'whatsapp:{receiver_phone}'
            
        message = client.messages.create(
            from_=from_whatsapp_number,
            to=receiver_phone,
            content_sid=content_sid,
            content_variables=json.dumps({"1": otp})
        )
        print(f"DEBUG: WhatsApp OTP sent using template. SID: {message.sid}")
        return True
    except Exception as e:
        print(f"DEBUG: WhatsApp OTP failed: {e}")
        return False

@app.route('/recover-id', methods=['GET', 'POST'])
def recover_id():
    if request.method == 'POST':
        class_val = request.form.get('class')
        section = request.form.get('section', '').upper()
        roll_no = request.form.get('roll_no')
        
        from google_sheets import GoogleSheetsDB
        db = GoogleSheetsDB()
        voter = db.get_voter_by_details(class_val, section, roll_no)
        
        if voter:
            flash('Identity recovered successfully.', 'success')
            return render_template('voting_system/recovery_result.html', voter_id=voter['voter_id'])
        else:
            flash('No matching student record found.', 'error')
            
    return render_template('voting_system/recover.html')

import time

def cleanup_old_videos():
    secure_dir = 'secure_sessions'
    if not os.path.exists(secure_dir):
        return
    now = time.time()
    for f in os.listdir(secure_dir):
        file_path = os.path.join(secure_dir, f)
        if os.stat(file_path).st_mtime < now - 24 * 3600:
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"DEBUG: Failed to delete old video {f}: {e}")

@app.route('/upload_session_video', methods=['POST'])
def upload_session_video():
    cleanup_old_videos()
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'No video file'}), 400
    
    video = request.files['video']
    metadata = request.form.get('metadata')
    if not metadata:
        return jsonify({'success': False, 'error': 'No metadata'}), 400
        
    try:
        meta = json.loads(metadata)
        filename = f"VOTESESSION_{meta['class']}{meta['section']}_{meta['roll']}_{meta['timestamp']}.webm"
        save_path = os.path.join('secure_sessions', filename)
        video.save(save_path)
        
        # Lightweight logging
        with open('session_log.txt', 'a') as f:
            f.write(f"{datetime.datetime.now().isoformat()} - ID: {meta.get('voter_id')} - Video Saved: YES\n")
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        otp = request.form.get('otp')
        
        if session.get('pending_admin_login') and otp:
            if otp == session.get('admin_otp'):
                session.pop('admin_otp', None)
                session.pop('pending_admin_login', None)
                session['admin_logged_in'] = True
                flash('Administrative session authorized. Welcome.', 'success')
                return redirect(url_for('admin_dashboard'))
            flash('Security Error: Incorrect OTP. Verification failed.', 'error')
            return render_template('admin/login.html', otp_sent=True)
            
        if password:
            if password in ADMIN_PASSWORDS:
                generated_otp = ''.join(random.choices(string.digits, k=6))
                print(f"DEBUG: Generated Admin OTP: {generated_otp}")
                session['admin_otp'] = generated_otp
                session['pending_admin_login'] = True
                
                admin_phone = os.environ.get('ADMIN_PHONE_NUMBER')
                otp_sent = False
                if admin_phone:
                    otp_sent = send_otp_whatsapp(admin_phone, generated_otp)
                
                if otp_sent:
                    flash(f'Security OTP dispatched via WhatsApp.', 'success')
                    session['show_otp_in_browser'] = generated_otp
                else:
                    flash('System Warning: OTP generated but delivery services failed.', 'error')
                
                return render_template('admin/login.html', otp_sent=True)
            else:
                flash('Access Denied: Invalid administrative password.', 'error')
            
    return render_template('admin/login.html', otp_sent=False)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    posts, candidates_map = get_posts_and_candidates()
    # Fetch all records including candidates for ID matching
    all_candidates_raw = db.get_all_records_safe('CANDIDATES')
    
    voters = db.get_all_voters()
    teachers = [v for v in voters if str(v.get('Class')) == 'TEACHER']
    
    return render_template('admin/dashboard.html', 
                          voters=voters, 
                          teachers=teachers,
                          votes=db.get_all_votes(),
                          candidates=candidates_map,
                          all_candidates_raw=all_candidates_raw,
                          posts=posts)

@app.route('/admin/teachers/generate')
def generate_teachers():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    voters = db.get_all_voters()
    teacher_count = sum(1 for v in voters if str(v.get('Class')) == 'TEACHER')
    
    if teacher_count < 100:
        for i in range(1, 101):
            t_id = f"T{1000 + i}"
            if not any(v.get('VotingID') == t_id for v in voters):
                db.add_voter({
                    'VotingID': t_id,
                    'Class': 'TEACHER',
                    'Section': 'STAFF',
                    'RollNo': str(i)
                })
        flash('100 Teachers generated successfully.', 'success')
    else:
        flash('Teachers already exist.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/auto-populate-candidates')
def auto_populate_candidates():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    candidates_list = [
        ('PRIME MINISTER', 'Aayush Patil', '10'),
        ('PRIME MINISTER', 'Gagan Kumbar', '10'),
        ('PRIME MINISTER', 'Veer Salgude', '10'),
        ('PRIME MINISTER', 'Bhuvan Kodag', '10'),
        ('PRIME MINISTER', 'Ankita Ullegaddi', '9'),
        ('PRIME MINISTER', 'Arya Bhagoji', '9'),
        ('PRIME MINISTER', 'Tejasvi Khokate', '9'),
        ('PRIME MINISTER', 'Prutha Dongre', '9'),
        ('CULTURAL MINISTER', 'Poorvi Kenchakkanavar', '10'),
        ('CULTURAL MINISTER', 'Adithi Hiremath', '10'),
        ('CULTURAL MINISTER', 'Poorvi Inchal', '9'),
        ('CULTURAL MINISTER', 'Nidhi Kumbar', '9'),
        ('CULTURAL MINISTER', 'Aditi P.', '9'),
        ('SPORTS MINISTER', 'Amogh Hiremath', '10'),
        ('SPORTS MINISTER', 'Ganesh K.', '10'),
        ('SPORTS MINISTER', 'Prarthana', '10'),
        ('SPORTS MINISTER', 'Lekhana D.', '9'),
        ('SPORTS MINISTER', 'Raj P.', '9'),
        ('SPORTS MINISTER', 'Sahana A.', '9'),
        ('FINANCE MINISTER', 'Ichcha Yargoppa', '10'),
        ('FINANCE MINISTER', 'Minal Varote', '10'),
        ('FINANCE MINISTER', 'Abdul Razak', '10'),
        ('FINANCE MINISTER', 'Pranjal A.', '9'),
        ('FINANCE MINISTER', 'Shrushti B.', '9'),
        ('FINANCE MINISTER', 'Komal N.', '9'),
        ('INFORMATION MINISTER', 'Neeta Nayak', '10'),
        ('INFORMATION MINISTER', 'Laxmi Patil', '10'),
        ('INFORMATION MINISTER', 'Pranamya Sarapur', '9'),
        ('INFORMATION MINISTER', 'Nivedita Patil', '9'),
        ('INFORMATION MINISTER', 'Tanvi M.', '9'),
        ('DISCIPLINE MINISTER', 'Sankalp Galabi', '10'),
        ('DISCIPLINE MINISTER', 'Anvita B.', '10'),
        ('DISCIPLINE MINISTER', 'Prayukta Yamakanmardi', '10'),
        ('DISCIPLINE MINISTER', 'Prakruti S.', '9'),
        ('DISCIPLINE MINISTER', 'Nidhi Kalsappanavar', '9'),
        ('DISCIPLINE MINISTER', 'Shrushti P.', '9'),
    ]
    
    existing_candidates = db.get_candidates_by_post()
    added_count = 0
    
    for post, name, active in candidates_list:
        clist = existing_candidates.get(post, [])
        if not any(c['name'] == name for c in clist):
            db.add_candidate(post, name, '', '', active)
            added_count += 1
            
    if added_count > 0:
        cache.data.pop('posts_candidates', None)
        flash(f'Auto-added {added_count} missing candidates.', 'success')
    else:
        flash('All candidates already present.', 'info')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/print/all')
def print_all():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    voters = db.get_all_voters()
    students = [v for v in voters if str(v.get('Class')) != 'TEACHER']
    teachers = [v for v in voters if str(v.get('Class')) == 'TEACHER']
    
    posts, candidates_map = get_posts_and_candidates()
    votes = db.get_all_votes()
    
    return render_template('admin/print_all.html', 
                          students=students,
                          teachers=teachers,
                          posts=posts,
                          candidates_map=candidates_map,
                          votes=votes)

@app.route('/admin/candidates/add', methods=['POST'])
def add_candidate():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    post = request.form.get('post')
    name = request.form.get('name')
    image_url = request.form.get('image_url', '')
    motto = request.form.get('motto', '')
    active = request.form.get('active', '10') # Default to 10 (Main)
    
    if post and name:
        db.add_candidate(post, name, image_url, motto, active)
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
