# School Election System

## Overview

A secure, eco-friendly digital school election system designed to replace paper ballots for Class 8 & 9 students. The system consists of two main modules: a Voter ID Generator (pre-election) and a Digital Voting System (election day). Built with Flask backend, HTML/CSS/JavaScript frontend, with Google Sheets planned as the database backend.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Application Structure
- **Framework**: Flask (Python) web application
- **Frontend**: Server-rendered HTML templates with Jinja2, vanilla CSS/JavaScript
- **Design Philosophy**: Apple-inspired, clean, professional UI suitable for school administration

### Core Modules

**Voter ID Generator (Pre-Election)**
- Generates unique 8-character alphanumeric voting IDs
- Validates eligibility (Class 8 & 9 only)
- Stores voter records with usage status tracking

**Digital Voting System (Election Day)**
- Step-by-step voting flow for multiple positions (Head Boy, Head Girl, Sports Captain, Cultural Secretary)
- Voter ID verification before ballot access
- One-vote-per-ID enforcement
- Confirmation screen before final submission

### Data Models
- **VOTERS_SHEET**: VotingID, Class, Section, RollNo, Used (YES/NO)
- **VOTES_SHEET**: VotingID, HeadBoy, HeadGirl, SportsCaptain, CulturalSecretary, Timestamp

### Authentication
- Simple password-based admin authentication
- Session-based state management
- Admin password configurable via environment variable `ADMIN_PASSWORD`

### Route Structure
- `/` - Home page with navigation
- `/voter-gen` - Voter ID generation form
- `/vote` - Voting verification and ballot flow
- `/admin` - Admin login
- Admin dashboard for monitoring registrations and votes

## External Dependencies

### Python Packages
- Flask 2.3.5 - Web framework
- requests - HTTP client (for API integrations)
- python-dotenv - Environment variable management

### Planned Integrations
- **Google Sheets API** - Intended to replace in-memory mock database for persistent storage
- Currently using in-memory Python lists as mock database

### Environment Variables
- `SESSION_SECRET` - Flask session encryption key
- `ADMIN_PASSWORD` - Admin panel access password

### CDN Resources
- Google Fonts (Inter, Poppins)
- Three.js (for unrelated NEO 3D visualizer feature)

### Deployment Target
- Designed for Render deployment
- Single laptop usage model with teacher supervision