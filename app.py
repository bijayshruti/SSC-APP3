"""
STAFF SELECTION COMMISSION (ER), KOLKATA
Centre Coordinator & Flying Squad Allocation System
Streamlit Web Application
Designed by Bijay Paswan

ENHANCED VERSION WITH COMPREHENSIVE DATE SELECTION SYSTEM
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys
import logging
import warnings
import hashlib
import base64
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import traceback
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter

warnings.filterwarnings('ignore')

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Create necessary directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

# File paths
CONFIG_FILE = DATA_DIR / "config.json"
DATA_FILE = DATA_DIR / "allocations_data.json"
REFERENCE_FILE = DATA_DIR / "allocation_references.json"
DELETED_RECORDS_FILE = DATA_DIR / "deleted_records.json"
LOGFILE = DATA_DIR / "app.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=LOGFILE
)

# Default remuneration rates
DEFAULT_RATES = {
    'multiple_shifts': 750,
    'single_shift': 450,
    'mock_test': 450,
    'ey_personnel': 5000
}

# ============================================================================
# SESSION STATE MANAGEMENT - COMPLETE INITIALIZATION
# ============================================================================

def initialize_session_state():
    """Initialize all session state variables"""
    # Data storage
    default_values = {
        'io_df': pd.DataFrame(),
        'venue_df': pd.DataFrame(),
        'ey_df': pd.DataFrame(),
        'allocation': [],
        'ey_allocation': [],
        'deleted_records': [],
        
        # Configuration
        'remuneration_rates': DEFAULT_RATES.copy(),
        'exam_data': {},
        'allocation_references': {},
        
        # Current state
        'current_exam_key': "",
        'exam_name': "",
        'exam_year': "",
        'mock_test_mode': False,
        'ey_allocation_mode': False,
        
        # UI state
        'selected_venue': "",
        'selected_role': "Centre Coordinator",
        'selected_dates': [],
        'selected_io': "",
        'selected_ey': "",
        
        # Enhanced Date Selection System
        'date_grid_state': {
            'normal_dates': {},
            'mock_dates': {},
            'ey_dates': {},
            'expanded_dates': {},
            'select_all': False
        },
        'date_grid_mode': "IO",
        'conflict_warning': None,
        
        # File upload tracking
        'io_master_loaded': False,
        'venue_master_loaded': False,
        'ey_master_loaded': False,
        
        # Current allocation state
        'current_allocation_person': None,
        'current_allocation_area': None,
        'current_allocation_role': None,
        'current_allocation_type': None,
        'current_allocation_ey_row': None,
        
        # UI flags
        'show_io_upload': False,
        'show_venue_upload': False,
        'show_ey_upload': False,
        'creating_new_ref_IO': False,
        'creating_new_ref_EY Personnel': False,
        
        # Current menu
        'menu': 'dashboard'
    }
    
    # Initialize all values
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# ============================================================================
# DATA PERSISTENCE FUNCTIONS
# ============================================================================

def load_all_data():
    """Load all data from files"""
    try:
        # Load config
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                st.session_state.remuneration_rates = config.get('remuneration_rates', DEFAULT_RATES.copy())
        
        # Load exam data
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                exam_data = json.load(f)
                st.session_state.exam_data = {}
                for exam_key, data in exam_data.items():
                    if isinstance(data, dict):
                        st.session_state.exam_data[exam_key] = data
                    else:
                        st.session_state.exam_data[exam_key] = {
                            'io_allocations': data,
                            'ey_allocations': []
                        }
        
        # Load reference data
        if REFERENCE_FILE.exists():
            with open(REFERENCE_FILE, 'r') as f:
                ref_data = json.load(f)
                st.session_state.allocation_references = ref_data
        
        # Load deleted records
        if DELETED_RECORDS_FILE.exists():
            with open(DELETED_RECORDS_FILE, 'r') as f:
                deleted_data = json.load(f)
                st.session_state.deleted_records = deleted_data
        
        # Load current allocations
        if st.session_state.current_exam_key and st.session_state.current_exam_key in st.session_state.exam_data:
            exam_data = st.session_state.exam_data[st.session_state.current_exam_key]
            st.session_state.allocation = exam_data.get('io_allocations', [])
            st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
        
        return True
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return False

def save_all_data():
    """Save all data to files"""
    try:
        # Update current exam data before saving
        if st.session_state.current_exam_key:
            if st.session_state.current_exam_key not in st.session_state.exam_data:
                st.session_state.exam_data[st.session_state.current_exam_key] = {
                    'io_allocations': [],
                    'ey_allocations': []
                }
            
            # Update allocations for current exam
            st.session_state.exam_data[st.session_state.current_exam_key]['io_allocations'] = st.session_state.allocation
            st.session_state.exam_data[st.session_state.current_exam_key]['ey_allocations'] = st.session_state.ey_allocation
        
        # Save config
        config = {
            'remuneration_rates': st.session_state.remuneration_rates,
            'last_saved': datetime.now().isoformat()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4, default=str)
        
        # Save exam data
        with open(DATA_FILE, 'w') as f:
            json.dump(st.session_state.exam_data, f, indent=4, default=str)
        
        # Save reference data
        with open(REFERENCE_FILE, 'w') as f:
            json.dump(st.session_state.allocation_references, f, indent=4, default=str)
        
        # Save deleted records
        with open(DELETED_RECORDS_FILE, 'w') as f:
            json.dump(st.session_state.deleted_records, f, indent=4, default=str)
        
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

# ============================================================================
# BACKUP MANAGEMENT
# ============================================================================

def create_backup(description=""):
    """Create a backup of current data"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        if description:
            backup_name += f"_{description.replace(' ', '_')}"
        backup_file = BACKUP_DIR / f"{backup_name}.json"
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'description': description,
            'exam_data': st.session_state.exam_data,
            'allocation_references': st.session_state.allocation_references,
            'remuneration_rates': st.session_state.remuneration_rates,
            'deleted_records': st.session_state.deleted_records,
            'current_exam_key': st.session_state.current_exam_key
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=4, default=str)
        
        return backup_file
    except Exception as e:
        return None

def restore_from_backup(backup_file):
    """Restore data from backup file"""
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        # Restore data
        st.session_state.exam_data = backup_data.get('exam_data', {})
        st.session_state.allocation_references = backup_data.get('allocation_references', {})
        st.session_state.remuneration_rates = backup_data.get('remuneration_rates', DEFAULT_RATES.copy())
        st.session_state.deleted_records = backup_data.get('deleted_records', [])
        st.session_state.current_exam_key = backup_data.get('current_exam_key', "")
        
        # Clear current allocations
        st.session_state.allocation = []
        st.session_state.ey_allocation = []
        
        # Load allocations if exam key exists
        if st.session_state.current_exam_key and st.session_state.current_exam_key in st.session_state.exam_data:
            exam_data = st.session_state.exam_data[st.session_state.current_exam_key]
            st.session_state.allocation = exam_data.get('io_allocations', [])
            st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
        
        # Save restored data
        save_all_data()
        
        return True
    except Exception as e:
        return False

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_default_master_data():
    """Load default master data for demonstration"""
    # Default IO data
    default_io_data = {
        'NAME': [
            'John Doe', 'Jane Smith', 'Robert Johnson', 
            'Emily Davis', 'Michael Wilson', 'Sarah Brown',
            'David Miller', 'Lisa Anderson', 'James Taylor',
            'Maria Thomas'
        ],
        'AREA': [
            'Kolkata', 'Howrah', 'Hooghly', 'Nadia', 
            'North 24 Parganas', 'South 24 Parganas',
            'Bardhaman', 'Birbhum', 'Bankura', 'Purulia'
        ],
        'CENTRE_CODE': ['1001', '1002', '1003', '2001', '2002', '3001', '3002', '4001', '4002', '5001'],
        'MOBILE': [
            '9876543210', '9876543211', '9876543212', '9876543213', '9876543214',
            '9876543215', '9876543216', '9876543217', '9876543218', '9876543219'
        ],
        'EMAIL': [
            'john@example.com', 'jane@example.com', 'robert@example.com',
            'emily@example.com', 'michael@example.com', 'sarah@example.com',
            'david@example.com', 'lisa@example.com', 'james@example.com',
            'maria@example.com'
        ],
        'DESIGNATION': [
            'Assistant Commissioner', 'Deputy Commissioner', 'Assistant Commissioner',
            'Section Officer', 'Assistant Section Officer', 'Section Officer',
            'Deputy Commissioner', 'Assistant Commissioner', 'Section Officer',
            'Assistant Section Officer'
        ],
        'BANK_NAME': ['SBI', 'PNB', 'BOB', 'SBI', 'PNB', 'BOB', 'SBI', 'PNB', 'BOB', 'SBI'],
        'ACCOUNT_NUMBER': ['1234567890', '2345678901', '3456789012', '4567890123', '5678901234',
                          '6789012345', '7890123456', '8901234567', '9012345678', '0123456789'],
        'IFSC_CODE': ['SBIN0001234', 'PNBN0012345', 'BARB0XXXXXX', 'SBIN0001234', 'PNBN0012345',
                     'BARB0XXXXXX', 'SBIN0001234', 'PNBN0012345', 'BARB0XXXXXX', 'SBIN0001234']
    }
    
    st.session_state.io_df = pd.DataFrame(default_io_data)
    st.session_state.io_master_loaded = True
    
    # Default venue data with dates for testing
    venues = ['Kolkata Main Centre', 'Howrah Centre', 'Hooghly Centre']
    venue_data = []
    
    for venue_idx, venue_name in enumerate(venues):
        centre_code = f'100{venue_idx + 1}'
        for day_offset in range(5):  # 5 days
            date = datetime.now().date() + timedelta(days=day_offset)
            date_str = date.strftime("%d-%m-%Y")
            for shift in ['Morning', 'Afternoon', 'Evening']:
                venue_data.append({
                    'VENUE': str(venue_name),
                    'DATE': str(date_str),
                    'SHIFT': str(shift),
                    'CENTRE_CODE': str(centre_code),
                    'ADDRESS': f'Address for {venue_name}',
                    'CENTRE NAME': str(venue_name),
                    'STATE': 'West Bengal',
                    'DISTRICT': str(venue_name.split()[0]),
                    'CAPACITY': 500 + (venue_idx * 100)
                })
    
    st.session_state.venue_df = pd.DataFrame(venue_data)
    st.session_state.venue_master_loaded = True
    
    # Default EY data
    default_ey_data = {
        'NAME': [
            'Dr. Amit Sharma', 'Prof. Priya Gupta', 'Ms. Anjali Chatterjee',
            'Mr. Rajesh Banerjee', 'Dr. Sunita Das', 'Prof. Ravi Kumar'
        ],
        'MOBILE': [
            '9876543201', '9876543202', '9876543203', '9876543204', '9876543205',
            '9876543206'
        ],
        'EMAIL': [
            'sharma@example.com', 'gupta@example.com', 'chatterjee@example.com',
            'banerjee@example.com', 'das@example.com', 'kumar@example.com'
        ],
        'ID_NUMBER': [f'EY00{i+1}' for i in range(6)],
        'DESIGNATION': [
            'Professor', 'Associate Professor', 'Assistant Professor',
            'Lecturer', 'Professor', 'Associate Professor'
        ],
        'DEPARTMENT': [
            'Mathematics', 'Physics', 'Chemistry', 'English',
            'History', 'Computer Science'
        ],
        'UNIVERSITY': [
            'University of Calcutta', 'Jadavpur University', 'Presidency University',
            'University of Calcutta', 'Jadavpur University', 'Presidency University'
        ]
    }
    
    st.session_state.ey_df = pd.DataFrame(default_ey_data)
    st.session_state.ey_master_loaded = True
    
    st.success("Default master data loaded successfully!")

# ============================================================================
# ENHANCED DATE SELECTION SYSTEM
# ============================================================================

def create_enhanced_date_selection_grid(allocation_type="IO"):
    """
    Create enhanced date selection grid with three modes:
    1. Normal Exam Mode (IO/Flying Squad)
    2. Mock Test Mode
    3. EY Personnel Mode
    """
    
    # Initialize selection state
    if 'date_grid_state' not in st.session_state:
        st.session_state.date_grid_state = {
            'normal_dates': {},
            'mock_dates': {},
            'ey_dates': {},
            'expanded_dates': {},
            'select_all': False
        }
    
    st.session_state.date_grid_mode = allocation_type
    
    # Create main container
    st.markdown("### 📅 Date & Shift Selection")
    
    # Mode selection (only show for IO mode)
    if allocation_type == "IO":
        col_mode1, col_mode2 = st.columns([2, 1])
        with col_mode1:
            mode = st.radio(
                "Selection Mode:",
                ["Normal Exam Dates", "Mock Test Dates"],
                horizontal=True,
                key="date_selection_mode"
            )
            st.session_state.mock_test_mode = (mode == "Mock Test Dates")
        
        with col_mode2:
            if st.button("🔁 Switch to EY Mode", use_container_width=True):
                st.session_state.ey_allocation_mode = True
                st.session_state.menu = "ey"
                st.rerun()
    else:
        # EY Mode
        st.session_state.mock_test_mode = False
        mode = "Normal Exam Dates"
    
    # ============================================
    # 1. NORMAL EXAM MODE (Centre Coordinators/Flying Squad)
    # ============================================
    if not st.session_state.mock_test_mode:
        
        # Venue selection for Normal Mode
        if allocation_type == "IO":
            venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
            if not venues:
                st.warning("No venues available. Please load venue data.")
                return []
            
            selected_venue = st.selectbox(
                "Select Venue:", 
                venues,
                key=f"venue_select_{allocation_type}",
                index=0
            )
            
            if selected_venue != st.session_state.selected_venue:
                st.session_state.selected_venue = selected_venue
                st.rerun()
            
            # Get venue data
            venue_data = st.session_state.venue_df[
                st.session_state.venue_df['VENUE'] == selected_venue
            ]
            selected_venues = [selected_venue]
        else:
            # EY Mode - multi-venue selection
            st.markdown("#### 🏢 Venue Selection")
            
            venues = sorted(st.session_state.venue_df['VENUE'].dropna().unique())
            if not venues:
                st.warning("No venues available. Please load venue data.")
                return []
            
            selected_venues = st.multiselect(
                "Select Venues (multiple allowed):",
                venues,
                default=[],
                key="ey_venue_select"
            )
            
            col_ey1, col_ey2 = st.columns(2)
            with col_ey1:
                if st.button("🎯 Select All Venues", use_container_width=True):
                    selected_venues = venues
                    st.rerun()
            
            with col_ey2:
                if st.button("🗑️ Clear All", type="secondary", use_container_width=True):
                    selected_venues = []
                    st.rerun()
            
            if not selected_venues:
                st.info("Select at least one venue to continue")
                return []
            
            # For EY mode, use first selected venue for date display
            selected_venue = selected_venues[0]
            venue_data = st.session_state.venue_df[
                st.session_state.venue_df['VENUE'] == selected_venue
            ]
        
        if venue_data.empty:
            st.warning(f"No data found for venue: {selected_venue}")
            return []
        
        # Get unique dates for selected venue
        unique_dates = sorted(venue_data['DATE'].dropna().unique())
        
        if not unique_dates:
            st.warning(f"No dates available for {selected_venue}")
            return []
        
        # Initialize date state if not exists
        venue_key = f"{st.session_state.current_exam_key}_{selected_venue}"
        if venue_key not in st.session_state.date_grid_state['normal_dates']:
            st.session_state.date_grid_state['normal_dates'][venue_key] = {}
        
        if venue_key not in st.session_state.date_grid_state['expanded_dates']:
            st.session_state.date_grid_state['expanded_dates'][venue_key] = {}
        
        # "Select All" checkbox
        all_dates_selected = True
        all_dates_partial = False
        
        # Check current selection status
        for date_str in unique_dates:
            date_key = f"{venue_key}_{date_str}"
            if date_key in st.session_state.date_grid_state['normal_dates'][venue_key]:
                date_state = st.session_state.date_grid_state['normal_dates'][venue_key][date_key]
                if not date_state.get('all_selected', False):
                    all_dates_selected = False
                    if any(date_state.get('shifts', {}).values()):
                        all_dates_partial = True
            else:
                all_dates_selected = False
        
        col_all, _ = st.columns([1, 3])
        with col_all:
            select_all = st.checkbox(
                "✓ Select All Dates/Shifts",
                value=all_dates_selected,
                key=f"select_all_{venue_key}"
            )
            
            if select_all != st.session_state.date_grid_state['select_all']:
                st.session_state.date_grid_state['select_all'] = select_all
                if select_all:
                    # Select all shifts for all dates
                    for date_str in unique_dates:
                        date_key = f"{venue_key}_{date_str}"
                        date_shifts = venue_data[venue_data['DATE'] == date_str]['SHIFT'].unique()
                        date_shifts = [str(s) for s in date_shifts if pd.notna(s) and str(s) != '']
                        
                        if date_key not in st.session_state.date_grid_state['normal_dates'][venue_key]:
                            st.session_state.date_grid_state['normal_dates'][venue_key][date_key] = {
                                'all_selected': False,
                                'shifts': {}
                            }
                        
                        for shift in date_shifts:
                            st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['shifts'][shift] = True
                        st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['all_selected'] = True
                else:
                    # Deselect all
                    for date_str in unique_dates:
                        date_key = f"{venue_key}_{date_str}"
                        if date_key in st.session_state.date_grid_state['normal_dates'][venue_key]:
                            for shift in st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['shifts']:
                                st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['shifts'][shift] = False
                            st.session_state.date_grid_state['normal_dates'][venue_key][date_key]['all_selected'] = False
                st.rerun()
        
        # Display dates in grid layout
        st.markdown(f"**Available dates for {selected_venue}:**")
        
        # Calculate number of columns based on date count
        num_dates = len(unique_dates)
        cols_per_row = 3 if num_dates > 6 else (4 if num_dates > 4 else min(4, num_dates))
        
        # Group dates into rows
        date_rows = [unique_dates[i:i + cols_per_row] for i in range(0, num_dates, cols_per_row)]
        
        for row_dates in date_rows:
            cols = st.columns(cols_per_row)
            for idx, date_str in enumerate(row_dates):
                with cols[idx]:
                    display_date_card(date_str, venue_data, venue_key, allocation_type)
        
        # Get selected date-shift combinations
        selected_date_shifts = get_selected_date_shifts(venue_key, unique_dates, venue_data, allocation_type, selected_venues)
        
        return selected_date_shifts
    
    # ============================================
    # 2. MOCK TEST MODE
    # ============================================
    else:
        st.markdown("#### 🎭 Mock Test Date Entry")
        
        col_mock1, col_mock2 = st.columns(2)
        with col_mock1:
            mock_date = st.date_input(
                "Mock Test Date:",
                value=datetime.now().date(),
                key="mock_date_input"
            )
        
        with col_mock2:
            mock_shift = st.selectbox(
                "Shift:",
                ["Morning", "Afternoon", "Evening"],
                key="mock_shift_select"
            )
        
        col_add, _ = st.columns([1, 3])
        with col_add:
            if st.button("➕ Add Mock Test Date", use_container_width=True):
                date_str = mock_date.strftime("%d-%m-%Y")
                venue_key = f"mock_{st.session_state.selected_venue}"
                
                if venue_key not in st.session_state.date_grid_state['mock_dates']:
                    st.session_state.date_grid_state['mock_dates'][venue_key] = {}
                
                date_key = f"{venue_key}_{date_str}"
                if date_key not in st.session_state.date_grid_state['mock_dates'][venue_key]:
                    st.session_state.date_grid_state['mock_dates'][venue_key][date_key] = {
                        'shifts': {},
                        'all_selected': False
                    }
                
                # Add shift
                st.session_state.date_grid_state['mock_dates'][venue_key][date_key]['shifts'][mock_shift] = True
                st.rerun()
        
        # Display mock dates
        venue_key = f"mock_{st.session_state.selected_venue}"
        if venue_key in st.session_state.date_grid_state['mock_dates']:
            mock_dates = list(st.session_state.date_grid_state['mock_dates'][venue_key].keys())
            mock_dates = [d.replace(f"{venue_key}_", "") for d in mock_dates]
            mock_dates = sorted(set(mock_dates))
            
            if mock_dates:
                st.markdown("#### Mock Test Dates Added:")
                
                # Display in grid
                cols_per_row = 3
                mock_rows = [mock_dates[i:i + cols_per_row] for i in range(0, len(mock_dates), cols_per_row)]
                
                for row_dates in mock_rows:
                    cols = st.columns(cols_per_row)
                    for idx, date_str in enumerate(row_dates):
                        with cols[idx]:
                            display_mock_date_card(date_str, venue_key)
                
                # Get selected mock date-shifts
                selected_date_shifts = get_selected_mock_date_shifts(venue_key)
                return selected_date_shifts
        
        st.info("Add mock test dates using the form above")
        return []

def display_date_card(date_str, venue_data, venue_key, allocation_type="IO"):
    """Display a date card in the grid"""
    
    # Get shifts for this date
    date_shifts_data = venue_data[venue_data['DATE'] == date_str]
    date_shifts = date_shifts_data['SHIFT'].unique()
    date_shifts = [str(shift) for shift in date_shifts if pd.notna(shift) and str(shift) != '']
    
    if not date_shifts:
        return
    
    # Initialize date state if not exists
    date_key = f"{venue_key}_{date_str}"
    if date_key not in st.session_state.date_grid_state['normal_dates'][venue_key]:
        st.session_state.date_grid_state['normal_dates'][venue_key][date_key] = {
            'all_selected': False,
            'shifts': {shift: False for shift in date_shifts}
        }
    
    # Get current state
    date_state = st.session_state.date_grid_state['normal_dates'][venue_key][date_key]
    
    # Calculate selection status
    selected_shifts = [shift for shift, selected in date_state['shifts'].items() if selected]
    all_selected = len(selected_shifts) == len(date_shifts)
    partially_selected = len(selected_shifts) > 0 and not all_selected
    none_selected = len(selected_shifts) == 0
    
    # Determine color based on selection
    if all_selected:
        bg_color = "#4CAF50"  # Green
        border_color = "#388E3C"
        status_text = "✓ All"
        emoji = "🟢"
    elif partially_selected:
        bg_color = "#FF9800"  # Orange
        border_color = "#F57C00"
        status_text = f"✓ {len(selected_shifts)}/{len(date_shifts)}"
        emoji = "🟠"
    else:
        bg_color = "#FFEB3B"  # Yellow
        border_color = "#FBC02D"
        status_text = f"{len(date_shifts)} shifts"
        emoji = "🟡"
    
    # Create clickable date card
    card_html = f"""
        <div style="
            background-color: {bg_color};
            color: #333;
            padding: 12px;
            border-radius: 8px;
            border: 2px solid {border_color};
            margin: 5px 0;
            cursor: pointer;
            text-align: center;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        ">
            <div style='font-size: 16px;'>{emoji} <strong>{date_str}</strong></div>
            <div style='font-size: 12px; margin-top: 5px;'>{status_text}</div>
        </div>
    """
    
    # Display card
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Handle click events
    col_click1, col_click2 = st.columns([1, 1])
    
    with col_click1:
        # Single click - toggle all shifts
        if st.button("📅 Toggle", key=f"toggle_{date_key}", use_container_width=True):
            if all_selected:
                # Deselect all
                for shift in date_shifts:
                    date_state['shifts'][shift] = False
                date_state['all_selected'] = False
            else:
                # Select all
                for shift in date_shifts:
                    date_state['shifts'][shift] = True
                date_state['all_selected'] = True
            st.rerun()
    
    with col_click2:
        # Double click - expand/collapse
        is_expanded = st.session_state.date_grid_state['expanded_dates'][venue_key].get(date_str, False)
        expand_label = "📖 Details" if not is_expanded else "📕 Hide"
        
        if st.button(expand_label, key=f"expand_{date_key}", use_container_width=True):
            st.session_state.date_grid_state['expanded_dates'][venue_key][date_str] = not is_expanded
            st.rerun()
    
    # Show shift selection if expanded
    if st.session_state.date_grid_state['expanded_dates'][venue_key].get(date_str, False):
        st.markdown("**Select Shifts:**")
        
        # Create columns for shifts
        shift_cols = st.columns(min(3, len(date_shifts)))
        
        for idx, shift in enumerate(sorted(date_shifts)):
            col_idx = idx % len(shift_cols)
            with shift_cols[col_idx]:
                shift_selected = st.checkbox(
                    f"⏰ {shift}",
                    value=date_state['shifts'][shift],
                    key=f"shift_{date_key}_{shift}"
                )
                if shift_selected != date_state['shifts'][shift]:
                    date_state['shifts'][shift] = shift_selected
                    # Update all_selected status
                    selected_now = [s for s, sel in date_state['shifts'].items() if sel]
                    date_state['all_selected'] = (len(selected_now) == len(date_shifts))
                    st.rerun()
        
        st.markdown("---")

def display_mock_date_card(date_str, venue_key):
    """Display a mock test date card in the grid"""
    
    date_key = f"{venue_key}_{date_str}"
    date_state = st.session_state.date_grid_state['mock_dates'][venue_key][date_key]
    
    # Get shifts
    date_shifts = list(date_state['shifts'].keys())
    selected_shifts = [shift for shift, selected in date_state['shifts'].items() if selected]
    
    all_selected = len(selected_shifts) == len(date_shifts)
    partially_selected = len(selected_shifts) > 0 and not all_selected
    
    # Determine color
    if all_selected:
        bg_color = "#2196F3"  # Blue for mock tests
        border_color = "#1976D2"
        status_text = "✓ All Mock"
        emoji = "🔵"
    elif partially_selected:
        bg_color = "#03A9F4"  # Light blue
        border_color = "#0288D1"
        status_text = f"✓ {len(selected_shifts)}/{len(date_shifts)}"
        emoji = "🔷"
    else:
        bg_color = "#B3E5FC"  # Very light blue
        border_color = "#81D4FA"
        status_text = f"{len(date_shifts)} mock"
        emoji = "◻️"
    
    # Create card
    card_html = f"""
        <div style="
            background-color: {bg_color};
            color: #333;
            padding: 12px;
            border-radius: 8px;
            border: 2px solid {border_color};
            margin: 5px 0;
            cursor: pointer;
            text-align: center;
            font-weight: bold;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        ">
            <div style='font-size: 16px;'>{emoji} <strong>{date_str}</strong></div>
            <div style='font-size: 12px; margin-top: 5px;'>{status_text} <small>(Mock)</small></div>
        </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Control buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("📅 Toggle", key=f"mock_toggle_{date_key}", use_container_width=True):
            if all_selected:
                # Deselect all
                for shift in date_shifts:
                    date_state['shifts'][shift] = False
            else:
                # Select all
                for shift in date_shifts:
                    date_state['shifts'][shift] = True
            st.rerun()
    
    with col2:
        if st.button("🗑️ Remove", key=f"mock_remove_{date_key}", type="secondary", use_container_width=True):
            del st.session_state.date_grid_state['mock_dates'][venue_key][date_key]
            st.rerun()
    
    with col3:
        # Show shift checkboxes inline
        shift_list = ", ".join([f"⏰{s}" if date_state['shifts'][s] else s for s in sorted(date_shifts)])
        st.caption(shift_list)

def get_selected_date_shifts(venue_key, unique_dates, venue_data, allocation_type="IO", selected_venues=None):
    """Get selected date-shift combinations for normal mode"""
    
    selected_date_shifts = []
    
    if selected_venues is None:
        selected_venues = [st.session_state.selected_venue]
    
    for date_str in unique_dates:
        date_key = f"{venue_key}_{date_str}"
        
        if (venue_key in st.session_state.date_grid_state['normal_dates'] and 
            date_key in st.session_state.date_grid_state['normal_dates'][venue_key]):
            
            date_state = st.session_state.date_grid_state['normal_dates'][venue_key][date_key]
            
            for shift, selected in date_state['shifts'].items():
                if selected:
                    # For EY mode: assign to ALL selected venues
                    if allocation_type == "EY":
                        for venue in selected_venues:
                            selected_date_shifts.append({
                                'venue': venue,
                                'date': date_str,
                                'shift': shift,
                                'is_mock': False,
                                'allocation_type': allocation_type
                            })
                    else:
                        # For IO mode: assign to single venue
                        selected_date_shifts.append({
                            'venue': st.session_state.selected_venue,
                            'date': date_str,
                            'shift': shift,
                            'is_mock': False,
                            'allocation_type': allocation_type
                        })
    
    return selected_date_shifts

def get_selected_mock_date_shifts(venue_key):
    """Get selected date-shift combinations for mock mode"""
    
    selected_date_shifts = []
    
    if venue_key in st.session_state.date_grid_state['mock_dates']:
        for date_key, date_state in st.session_state.date_grid_state['mock_dates'][venue_key].items():
            date_str = date_key.replace(f"{venue_key}_", "")
            
            for shift, selected in date_state['shifts'].items():
                if selected:
                    selected_date_shifts.append({
                        'venue': st.session_state.selected_venue,
                        'date': date_str,
                        'shift': shift,
                        'is_mock': True,
                        'allocation_type': "IO"
                    })
    
    return selected_date_shifts

# ============================================================================
# CONFLICT CHECKING SYSTEM
# ============================================================================

def check_allocation_conflict_enhanced(person_name, date_info, role, allocation_type):
    """
    Enhanced conflict checking with detailed messages
    """
    
    venue = date_info['venue']
    date = date_info['date']
    shift = date_info['shift']
    is_mock = date_info.get('is_mock', False)
    
    if allocation_type == "IO":
        allocations = st.session_state.allocation
        
        # 1. Check for exact duplicate
        duplicate = any(
            alloc['IO Name'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] == venue and 
            alloc['Role'] == role and
            alloc.get('Mock Test', False) == is_mock
            for alloc in allocations
            if alloc.get('Exam') == st.session_state.current_exam_key
        )
        
        if duplicate:
            return True, f"❌ Duplicate allocation! {person_name} is already allocated to {venue} on {date} ({shift}) as {role}."
        
        # 2. For Centre Coordinator: Cannot be at multiple venues same date/shift
        if role == "Centre Coordinator":
            conflict = any(
                alloc['IO Name'] == person_name and 
                alloc['Date'] == date and 
                alloc['Shift'] == shift and 
                alloc['Venue'] != venue and
                alloc['Role'] == "Centre Coordinator"
                for alloc in allocations
                if alloc.get('Exam') == st.session_state.current_exam_key
            )
            
            if conflict:
                existing_venue = next(
                    alloc['Venue'] for alloc in allocations 
                    if alloc['IO Name'] == person_name and 
                       alloc['Date'] == date and 
                       alloc['Shift'] == shift and
                       alloc['Role'] == "Centre Coordinator" and
                       alloc.get('Exam') == st.session_state.current_exam_key
                )
                return True, f"❌ Centre Coordinator conflict! {person_name} is already allocated to {existing_venue} on {date} ({shift})."
        
        # 3. For Flying Squad: Allow multiple venues but warn
        elif role == "Flying Squad":
            existing_venues = [
                alloc['Venue'] for alloc in allocations 
                if alloc['IO Name'] == person_name and 
                   alloc['Date'] == date and 
                   alloc['Shift'] == shift and
                   alloc['Role'] == "Flying Squad" and
                   alloc.get('Exam') == st.session_state.current_exam_key
            ]
            
            if existing_venues:
                if venue in existing_venues:
                    return False, ""  # Same venue, handled by duplicate check
                
                # Check if this would exceed reasonable limits
                if len(existing_venues) >= 3:
                    return True, f"❌ Too many venues! {person_name} is already assigned to {len(existing_venues)} venues on {date} ({shift}). Maximum 3 venues allowed."
                
                return False, f"⚠️ Warning: {person_name} is already allocated to {', '.join(existing_venues)} on {date} ({shift}). Do you want to assign to additional venue {venue}?"
    
    elif allocation_type == "EY":
        allocations = st.session_state.ey_allocation
        
        # 1. Check for exact duplicate
        duplicate = any(
            alloc['EY Personnel'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] == venue
            for alloc in allocations
            if alloc.get('Exam') == st.session_state.current_exam_key
        )
        
        if duplicate:
            return True, f"❌ Duplicate EY allocation! {person_name} is already allocated to {venue} on {date} ({shift})."
        
        # 2. EY Personnel: Cannot be at multiple venues same date/shift
        conflict = any(
            alloc['EY Personnel'] == person_name and 
            alloc['Date'] == date and 
            alloc['Shift'] == shift and 
            alloc['Venue'] != venue
            for alloc in allocations
            if alloc.get('Exam') == st.session_state.current_exam_key
        )
        
        if conflict:
            existing_venue = next(
                alloc['Venue'] for alloc in allocations 
                if alloc['EY Personnel'] == person_name and 
                   alloc['Date'] == date and 
                   alloc['Shift'] == shift and
                   alloc.get('Exam') == st.session_state.current_exam_key
            )
            return True, f"❌ EY Personnel conflict! {person_name} is already allocated to {existing_venue} on {date} ({shift})."
        
        # 3. Check for excessive assignments
        same_day_assignments = [
            alloc for alloc in allocations
            if alloc['EY Personnel'] == person_name and 
               alloc['Date'] == date and
               alloc.get('Exam') == st.session_state.current_exam_key
        ]
        
        if len(same_day_assignments) >= 4:
            return True, f"❌ Excessive workload! {person_name} already has {len(same_day_assignments)} shifts on {date}. Maximum 4 shifts allowed per day."
    
    return False, ""

def handle_conflict_warning(warning_message, date_info):
    """Handle conflict warnings with user confirmation"""
    
    # Store warning in session state
    st.session_state.conflict_warning = {
        'message': warning_message,
        'date_info': date_info,
        'confirmed': False
    }
    
    # Show warning dialog
    st.warning(warning_message)
    
    col_warn1, col_warn2 = st.columns(2)
    with col_warn1:
        if st.button("✅ Proceed Anyway", type="primary"):
            st.session_state.conflict_warning['confirmed'] = True
            st.rerun()
    
    with col_warn2:
        if st.button("❌ Cancel", type="secondary"):
            st.session_state.conflict_warning = None
            st.rerun()
    
    return False

# ============================================================================
# REFERENCE MANAGEMENT
# ============================================================================

def get_or_create_reference(allocation_type):
    """Get existing reference or create new one"""
    exam_key = st.session_state.current_exam_key
    if not exam_key:
        st.warning("Please select or create an exam first")
        return None
    
    if exam_key not in st.session_state.allocation_references:
        st.session_state.allocation_references[exam_key] = {}
    
    role_key = allocation_type
    
    # Check if reference exists
    if role_key in st.session_state.allocation_references[exam_key]:
        existing_ref = st.session_state.allocation_references[exam_key][role_key]
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(f"📝 Use Existing Reference", key=f"use_existing_{allocation_type}"):
                return existing_ref
        
        with col2:
            if st.button(f"🆕 Create New Reference", key=f"new_ref_{allocation_type}"):
                st.session_state[f"creating_new_ref_{allocation_type}"] = True
                st.rerun()
        
        # Display existing reference info
        st.info(f"**Existing Reference:** Order No. {existing_ref.get('order_no', 'N/A')}, Page No. {existing_ref.get('page_no', 'N/A')}")
        
        if f"creating_new_ref_{allocation_type}" in st.session_state and st.session_state[f"creating_new_ref_{allocation_type}"]:
            return create_reference_form(allocation_type)
        
        return None
    else:
        return create_reference_form(allocation_type)

def create_reference_form(allocation_type):
    """Create a form for entering reference details"""
    st.markdown(f"### 📋 Enter Reference for {allocation_type}")
    
    order_no = st.text_input("Order No.:", key=f"order_no_{allocation_type}")
    page_no = st.text_input("Page No.:", key=f"page_no_{allocation_type}")
    remarks = st.text_area("Remarks (Optional):", key=f"remarks_{allocation_type}", height=100)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save Reference", key=f"save_ref_{allocation_type}"):
            if order_no and page_no:
                exam_key = st.session_state.current_exam_key
                if exam_key not in st.session_state.allocation_references:
                    st.session_state.allocation_references[exam_key] = {}
                
                st.session_state.allocation_references[exam_key][allocation_type] = {
                    'order_no': order_no,
                    'page_no': page_no,
                    'remarks': remarks,
                    'timestamp': datetime.now().isoformat(),
                    'allocation_type': allocation_type
                }
                
                save_all_data()
                st.success("✅ Reference saved successfully!")
                
                if f"creating_new_ref_{allocation_type}" in st.session_state:
                    st.session_state[f"creating_new_ref_{allocation_type}"] = False
                
                st.rerun()
                return st.session_state.allocation_references[exam_key][allocation_type]
            else:
                st.error("Please enter both Order No. and Page No.")
    
    with col2:
        if st.button("❌ Cancel", key=f"cancel_ref_{allocation_type}"):
            if f"creating_new_ref_{allocation_type}" in st.session_state:
                st.session_state[f"creating_new_ref_{allocation_type}"] = False
            st.rerun()
            return None
    
    return None

# ============================================================================
# ALLOCATION FUNCTIONS
# ============================================================================

def perform_allocation_with_conflict_check(person_name, selected_date_shifts, role, allocation_type, ref_data):
    """Perform allocation with comprehensive conflict checking"""
    
    allocation_count = 0
    conflicts = []
    warnings_confirmed = []
    
    for date_info in selected_date_shifts:
        # Check for conflicts
        is_conflict, message = check_allocation_conflict_enhanced(
            person_name, date_info, role, allocation_type
        )
        
        if is_conflict:
            conflicts.append({
                'date_info': date_info,
                'message': message,
                'type': 'error'
            })
            continue
        
        # Check for warnings (Flying Squad multiple venues)
        if "Warning:" in message:
            warning_key = f"{person_name}_{date_info['date']}_{date_info['shift']}"
            if warning_key not in warnings_confirmed:
                if 'conflict_warning' in st.session_state and st.session_state.conflict_warning['confirmed']:
                    warnings_confirmed.append(warning_key)
                else:
                    if handle_conflict_warning(message, date_info):
                        warnings_confirmed.append(warning_key)
                    continue
        
        # Create allocation
        if allocation_type == "IO":
            allocation = {
                'Sl. No.': len(st.session_state.allocation) + allocation_count + 1,
                'Venue': date_info['venue'],
                'Date': date_info['date'],
                'Shift': date_info['shift'],
                'IO Name': person_name,
                'Area': st.session_state.current_allocation_area,
                'Role': role,
                'Mock Test': date_info['is_mock'],
                'Exam': st.session_state.current_exam_key,
                'Order No.': ref_data['order_no'],
                'Page No.': ref_data['page_no'],
                'Reference Remarks': ref_data.get('remarks', ''),
                'Timestamp': datetime.now().isoformat()
            }
            
            st.session_state.allocation.append(allocation)
        
        elif allocation_type == "EY":
            ey_row = st.session_state.current_allocation_ey_row
            
            allocation = {
                'Sl. No.': len(st.session_state.ey_allocation) + allocation_count + 1,
                'Venue': date_info['venue'],
                'Date': date_info['date'],
                'Shift': date_info['shift'],
                'EY Personnel': person_name,
                'Mobile': ey_row.get('MOBILE', ''),
                'Email': ey_row.get('EMAIL', ''),
                'ID Number': ey_row.get('ID_NUMBER', ''),
                'Designation': ey_row.get('DESIGNATION', ''),
                'Department': ey_row.get('DEPARTMENT', ''),
                'Mock Test': False,
                'Exam': st.session_state.current_exam_key,
                'Rate (₹)': st.session_state.remuneration_rates['ey_personnel'],
                'Order No.': ref_data['order_no'],
                'Page No.': ref_data['page_no'],
                'Reference Remarks': ref_data.get('remarks', ''),
                'Timestamp': datetime.now().isoformat()
            }
            
            st.session_state.ey_allocation.append(allocation)
        
        allocation_count += 1
    
    return allocation_count, conflicts, warnings_confirmed

# ============================================================================
# DASHBOARD MODULE
# ============================================================================

def show_dashboard():
    """Display main dashboard"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📊 SYSTEM DASHBOARD</h1>
            <p>Enhanced Date Selection System</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Quick Stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div style='background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;'>
                <h3 style='color: #4169e1;'>👨‍💼 IO Allocations</h3>
                <h1 style='color: #2c3e50;'>{len(st.session_state.allocation)}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div style='background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;'>
                <h3 style='color: #9370db;'>👁️ EY Allocations</h3>
                <h1 style='color: #2c3e50;'>{len(st.session_state.ey_allocation)}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div style='background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;'>
                <h3 style='color: #20b2aa;'>📚 Total Exams</h3>
                <h1 style='color: #2c3e50;'>{len(st.session_state.exam_data)}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        current_exam = st.session_state.current_exam_key or "Not Selected"
        st.markdown(f"""
            <div style='background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;'>
                <h3 style='color: #ff8c00;'>🎯 Active Exam</h3>
                <h4 style='color: #2c3e50;'>{current_exam[:20]}{'...' if len(current_exam) > 20 else ''}</h4>
            </div>
        """, unsafe_allow_html=True)
    
    # System Features
    st.markdown("### 🚀 Enhanced Date Selection System")
    
    col_feat1, col_feat2, col_feat3 = st.columns(3)
    
    with col_feat1:
        st.markdown("""
            <div style='padding: 15px; background: #f8f9fa; border-radius: 8px;'>
                <h4>📅 Normal Exam Mode</h4>
                <p>• Load dates from venue Excel</p>
                <p>• Grid layout with color coding</p>
                <p>• Single-click to toggle all shifts</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_feat2:
        st.markdown("""
            <div style='padding: 15px; background: #f8f9fa; border-radius: 8px;'>
                <h4>🎭 Mock Test Mode</h4>
                <p>• Manual date entry</p>
                <p>• Distinct blue styling</p>
                <p>• Separate from regular dates</p>
            </div>
        """, unsafe_allow_html=True)
    
    with col_feat3:
        st.markdown("""
            <div style='padding: 15px; background: #f8f9fa; border-radius: 8px;'>
                <h4>👁️ EY Personnel Mode</h4>
                <p>• Multi-venue selection</p>
                <p>• Assign to all selected venues</p>
                <p>• Advanced conflict checking</p>
            </div>
        """, unsafe_allow_html=True)
    
    # Quick Actions
    st.markdown("### ⚡ Quick Actions")
    
    col_act1, col_act2, col_act3 = st.columns(3)
    
    with col_act1:
        if st.button("📥 Load Default Data", use_container_width=True):
            load_default_master_data()
            st.rerun()
    
    with col_act2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            load_all_data()
            st.rerun()
    
    with col_act3:
        if st.button("📊 View All Reports", use_container_width=True):
            st.session_state.menu = "reports"
            st.rerun()

# ============================================================================
# EXAM MANAGEMENT MODULE
# ============================================================================

def show_exam_management():
    """Display exam management interface"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #20b2aa 0%, #3cb371 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📝 EXAM MANAGEMENT</h1>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🆕 Create / Update Exam")
        
        exam_name = st.text_input("Exam Name:", placeholder="e.g., Combined Graduate Level Examination")
        
        current_year = datetime.now().year
        year_options = [str(y) for y in range(current_year - 5, current_year + 3)]
        exam_year = st.selectbox("Exam Year:", year_options, index=0)
        
        if st.button("✅ Create/Update Exam", use_container_width=True):
            if exam_name.strip():
                exam_key = f"{exam_name.strip()} - {exam_year}"
                
                st.session_state.current_exam_key = exam_key
                st.session_state.exam_name = exam_name.strip()
                st.session_state.exam_year = exam_year
                
                if exam_key not in st.session_state.exam_data:
                    st.session_state.exam_data[exam_key] = {
                        'io_allocations': [],
                        'ey_allocations': []
                    }
                    st.success(f"🎉 New exam '{exam_key}' created!")
                else:
                    exam_data = st.session_state.exam_data[exam_key]
                    if isinstance(exam_data, dict):
                        st.session_state.allocation = exam_data.get('io_allocations', [])
                        st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
                    else:
                        st.session_state.allocation = exam_data
                        st.session_state.ey_allocation = []
                    
                    st.success(f"📂 Exam '{exam_key}' loaded!")
                
                save_all_data()
                st.rerun()
            else:
                st.error("Please enter an exam name")
    
    with col2:
        st.markdown("### 📂 Select Existing Exam")
        
        exams = sorted(st.session_state.exam_data.keys())
        if exams:
            selected_exam = st.selectbox("Choose Exam:", exams, index=0)
            
            if st.button("📥 Load Selected Exam", use_container_width=True):
                st.session_state.current_exam_key = selected_exam
                
                exam_data = st.session_state.exam_data[selected_exam]
                if isinstance(exam_data, dict):
                    st.session_state.allocation = exam_data.get('io_allocations', [])
                    st.session_state.ey_allocation = exam_data.get('ey_allocations', [])
                else:
                    st.session_state.allocation = exam_data
                    st.session_state.ey_allocation = []
                
                if " - " in selected_exam:
                    name, year = selected_exam.split(" - ", 1)
                    st.session_state.exam_name = name
                    st.session_state.exam_year = year
                
                st.success(f"✅ Exam loaded successfully!")
                st.rerun()
        else:
            st.info("No exams available")

# ============================================================================
# CENTRE COORDINATOR MODULE - WITH ENHANCED DATE SELECTION
# ============================================================================

def show_centre_coordinator():
    """Display Centre Coordinator allocation interface"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #4169e1 0%, #6ca0dc 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>👨‍💼 CENTRE COORDINATOR ALLOCATION</h1>
            <p>Enhanced Date Selection System</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Check if exam is selected
    if not st.session_state.current_exam_key:
        st.error("⚠️ Please select or create an exam first")
        return
    
    # Master Data Loading
    st.markdown("### 📁 Master Data Management")
    
    col_data1, col_data2, col_data3 = st.columns(3)
    
    with col_data1:
        if st.button("📤 Load IO Master", use_container_width=True):
            st.session_state.show_io_upload = True
    
    with col_data2:
        if st.button("📤 Load Venue List", use_container_width=True):
            st.session_state.show_venue_upload = True
    
    # Show file uploaders
    if st.session_state.show_io_upload:
        uploaded_io = st.file_uploader("Upload Centre Coordinator Master (Excel)", type=['xlsx', 'xls'], key="io_master_upload")
        if uploaded_io:
            try:
                st.session_state.io_df = pd.read_excel(uploaded_io)
                st.session_state.io_df.columns = [str(col).strip().upper() for col in st.session_state.io_df.columns]
                
                required_cols = ["NAME", "AREA", "CENTRE_CODE"]
                missing_cols = [col for col in required_cols if col not in st.session_state.io_df.columns]
                
                if missing_cols:
                    st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
                else:
                    st.session_state.io_master_loaded = True
                    st.success(f"✅ Loaded {len(st.session_state.io_df)} IO records")
                    st.session_state.show_io_upload = False
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    if st.session_state.show_venue_upload:
        uploaded_venue = st.file_uploader("Upload Venue List (Excel)", type=['xlsx', 'xls'], key="venue_upload")
        if uploaded_venue:
            try:
                st.session_state.venue_df = pd.read_excel(uploaded_venue)
                st.session_state.venue_df.columns = [str(col).strip().upper() for col in st.session_state.venue_df.columns]
                
                required_cols = ["VENUE", "DATE", "SHIFT"]
                missing_cols = [col for col in required_cols if col not in st.session_state.venue_df.columns]
                
                if missing_cols:
                    st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
                else:
                    if 'DATE' in st.session_state.venue_df.columns:
                        st.session_state.venue_df['DATE'] = pd.to_datetime(
                            st.session_state.venue_df['DATE'], errors='coerce'
                        ).dt.strftime('%d-%m-%Y')
                    
                    if 'SHIFT' in st.session_state.venue_df.columns:
                        st.session_state.venue_df['SHIFT'] = st.session_state.venue_df['SHIFT'].astype(str).str.strip()
                        st.session_state.venue_df['SHIFT'] = st.session_state.venue_df['SHIFT'].replace('nan', '')
                    
                    if 'VENUE' in st.session_state.venue_df.columns:
                        st.session_state.venue_df['VENUE'] = st.session_state.venue_df['VENUE'].astype(str).str.strip()
                    
                    st.session_state.venue_df = st.session_state.venue_df[
                        (st.session_state.venue_df['VENUE'].notna()) & 
                        (st.session_state.venue_df['VENUE'] != '') &
                        (st.session_state.venue_df['DATE'].notna()) & 
                        (st.session_state.venue_df['DATE'] != '')
                    ]
                    
                    st.session_state.venue_master_loaded = True
                    st.success(f"✅ Loaded {len(st.session_state.venue_df)} venue records")
                    st.session_state.show_venue_upload = False
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Check required data
    if not st.session_state.venue_master_loaded:
        st.warning("⚠️ Please load venue list first")
        return
    
    if not st.session_state.io_master_loaded:
        st.warning("⚠️ Please load IO master data first")
        return
    
    # Selection Parameters
    st.markdown("### 🎯 Selection Parameters")
    
    col_param1, col_param2 = st.columns(2)
    
    with col_param1:
        # Role selection
        role = st.selectbox("Select Role:", ["Centre Coordinator", "Flying Squad"], key="role_select")
        st.session_state.selected_role = role
    
    # Enhanced Date Selection
    if st.session_state.mock_test_mode:
        st.info("🎭 **Mock Test Mode Active** - Enter mock test dates manually")
    
    # Use enhanced date selection system
    selected_date_shifts = create_enhanced_date_selection_grid("IO")
    
    # Display selection summary
    if selected_date_shifts:
        # Group by date for better display
        date_groups = {}
        for ds in selected_date_shifts:
            date_key = ds['date']
            if date_key not in date_groups:
                date_groups[date_key] = []
            shift_info = f"{ds['shift']}{' (Mock)' if ds['is_mock'] else ''}"
            if ds['venue'] not in [v for v, _ in date_groups[date_key]]:
                date_groups[date_key].append((ds['venue'], shift_info))
        
        st.success(f"✅ Selected {len(selected_date_shifts)} date-shift combination(s)")
        
        with st.expander("📋 View Selection Details"):
            for date, venues in sorted(date_groups.items()):
                st.write(f"**{date}:**")
                for venue, shift in venues:
                    st.write(f"  - {venue}: {shift}")
    else:
        st.info("Select dates above to continue")
    
    # IO Selection
    st.markdown("### 👥 Centre Coordinator Selection")
    
    # Filter IOs
    filtered_io = st.session_state.io_df.copy()
    
    # Search functionality
    search_term = st.text_input("🔍 Search Centre Coordinator:", placeholder="Search by name or area...")
    
    if search_term:
        filtered_io = filtered_io[
            (filtered_io['NAME'].str.lower().str.contains(search_term.lower())) |
            (filtered_io['AREA'].str.lower().str.contains(search_term.lower()))
        ]
    
    if not filtered_io.empty and selected_date_shifts:
        st.write(f"**Available Centre Coordinators ({len(filtered_io)} found):**")
        
        # Display IOs
        for idx, row in filtered_io.iterrows():
            name = row.get('NAME', 'N/A')
            area = row.get('AREA', 'N/A')
            designation = row.get('DESIGNATION', 'N/A')
            
            # Check existing allocations
            existing_allocations = [
                a for a in st.session_state.allocation 
                if a['IO Name'] == name and a.get('Exam') == st.session_state.current_exam_key
            ]
            
            with st.expander(f"👤 {name} ({area})", expanded=False):
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    st.write(f"**Designation:** {designation}")
                    st.write(f"**Area:** {area}")
                
                with col_info2:
                    st.write(f"**Mobile:** {row.get('MOBILE', 'N/A')}")
                    st.write(f"**Email:** {row.get('EMAIL', 'N/A')}")
                
                # Allocation button
                if st.button(f"✅ Allocate {name}", key=f"alloc_btn_{idx}", use_container_width=True):
                    st.session_state.current_allocation_person = name
                    st.session_state.current_allocation_area = area
                    st.session_state.current_allocation_role = role
                    st.session_state.current_allocation_type = "IO"
                    st.rerun()
    elif not selected_date_shifts:
        st.info("Select dates above to enable allocation")
    else:
        st.warning("No Centre Coordinators found")
    
    # Handle allocation
    if st.session_state.current_allocation_person and st.session_state.current_allocation_type == "IO":
        # Show reference selection
        st.markdown(f"### 📋 Reference for {st.session_state.current_allocation_person}")
        ref_data = get_or_create_reference(st.session_state.current_allocation_role)
        
        if ref_data is not None:
            # Perform allocation
            allocation_count, conflicts, warnings = perform_allocation_with_conflict_check(
                st.session_state.current_allocation_person,
                selected_date_shifts,
                st.session_state.current_allocation_role,
                "IO",
                ref_data
            )
            
            # Update exam data
            exam_key = st.session_state.current_exam_key
            if exam_key not in st.session_state.exam_data:
                st.session_state.exam_data[exam_key] = {}
            
            st.session_state.exam_data[exam_key]['io_allocations'] = st.session_state.allocation
            
            # Save data
            save_all_data()
            
            # Clear allocation state
            st.session_state.current_allocation_person = None
            st.session_state.current_allocation_area = None
            st.session_state.current_allocation_role = None
            st.session_state.current_allocation_type = None
            
            if allocation_count > 0:
                success_msg = f"✅ Allocated {st.session_state.current_allocation_person} to {allocation_count} date-shift combination(s)"
                
                if warnings:
                    success_msg += f"\n\n⚠️ {len(warnings)} warning(s) confirmed"
                
                if conflicts:
                    conflict_details = "\n".join([c['message'] for c in conflicts[:3]])
                    if len(conflicts) > 3:
                        conflict_details += f"\n... and {len(conflicts) - 3} more"
                    st.error(f"❌ {len(conflicts)} conflict(s) prevented allocation:\n\n{conflict_details}")
                
                st.success(success_msg)
                st.rerun()
            else:
                if conflicts:
                    st.error(f"❌ No allocations made due to {len(conflicts)} conflict(s)")
                else:
                    st.error("❌ No allocations made")
    
    # Current Allocations Display
    if st.session_state.allocation:
        st.markdown("---")
        st.markdown("### 📋 Current Allocations")
        
        alloc_df = pd.DataFrame(st.session_state.allocation)
        
        # Filter by current exam
        current_allocations = alloc_df[alloc_df['Exam'] == st.session_state.current_exam_key]
        
        if not current_allocations.empty:
            st.dataframe(
                current_allocations[['Sl. No.', 'IO Name', 'Venue', 'Date', 'Shift', 'Role', 'Mock Test']],
                use_container_width=True,
                hide_index=True
            )

# ============================================================================
# EY PERSONNEL MODULE - WITH ENHANCED DATE SELECTION
# ============================================================================

def show_ey_personnel():
    """Display EY Personnel allocation interface"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #9370db 0%, #8a2be2 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>👁️ EY PERSONNEL ALLOCATION</h1>
            <p>Multi-Venue Date Selection System</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Check if exam is selected
    if not st.session_state.current_exam_key:
        st.error("⚠️ Please select or create an exam first")
        return
    
    # Mode switch
    col_mode1, col_mode2 = st.columns(2)
    with col_mode1:
        if st.checkbox("👨‍💼 Switch to Centre Coordinator"):
            st.session_state.menu = "io"
            st.rerun()
    
    # Master Data Loading
    st.markdown("### 📁 EY Master Data")
    
    if st.button("📤 Load EY Master", use_container_width=True):
        st.session_state.show_ey_upload = True
    
    # EY Rate Setting
    ey_rate = st.number_input("💰 EY Rate per Day (₹):", value=st.session_state.remuneration_rates['ey_personnel'], min_value=0, step=100)
    if ey_rate != st.session_state.remuneration_rates['ey_personnel']:
        st.session_state.remuneration_rates['ey_personnel'] = ey_rate
        save_all_data()
    
    # Show EY uploader
    if st.session_state.show_ey_upload:
        uploaded_ey = st.file_uploader("Upload EY Personnel Master (Excel)", type=['xlsx', 'xls'], key="ey_master_upload")
        if uploaded_ey:
            try:
                st.session_state.ey_df = pd.read_excel(uploaded_ey)
                st.session_state.ey_df.columns = [str(col).strip().upper() for col in st.session_state.ey_df.columns]
                
                if 'NAME' not in st.session_state.ey_df.columns:
                    st.error("❌ Missing required column: NAME")
                else:
                    optional_cols = ["MOBILE", "EMAIL", "ID_NUMBER", "DESIGNATION", "DEPARTMENT"]
                    for col in optional_cols:
                        if col not in st.session_state.ey_df.columns:
                            st.session_state.ey_df[col] = ""
                    
                    st.session_state.ey_master_loaded = True
                    st.success(f"✅ Loaded {len(st.session_state.ey_df)} EY personnel records")
                    st.session_state.show_ey_upload = False
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    # Check for required data
    if not st.session_state.ey_master_loaded:
        st.warning("⚠️ Please load EY master data first")
        return
    
    if not st.session_state.venue_master_loaded:
        st.warning("⚠️ Please load venue list from Centre Coordinator section")
        return
    
    # Enhanced Date Selection for EY Mode
    selected_date_shifts = create_enhanced_date_selection_grid("EY")
    
    if selected_date_shifts:
        # Display selection summary
        st.success(f"✅ Selected {len(selected_date_shifts)} date-shift-venue combination(s)")
        
        # Group by venue for better display
        venue_groups = {}
        for ds in selected_date_shifts:
            venue = ds['venue']
            if venue not in venue_groups:
                venue_groups[venue] = []
            date_shift = f"{ds['date']} ({ds['shift']})"
            if date_shift not in venue_groups[venue]:
                venue_groups[venue].append(date_shift)
        
        with st.expander("📋 View Allocation Plan"):
            for venue, dates in sorted(venue_groups.items()):
                st.write(f"**{venue}:**")
                for date_shift in sorted(dates):
                    st.write(f"  - {date_shift}")
    else:
        st.info("Select dates above to continue")
        return
    
    # EY Personnel Selection
    st.markdown("### 👥 EY Personnel Selection")
    
    # Search functionality
    search_term = st.text_input("🔍 Search EY Personnel:", placeholder="Search by name, department, or ID...")
    
    if search_term:
        filtered_ey = st.session_state.ey_df[
            (st.session_state.ey_df['NAME'].str.lower().str.contains(search_term.lower())) |
            (st.session_state.ey_df['DEPARTMENT'].str.lower().str.contains(search_term.lower()))
        ]
    else:
        filtered_ey = st.session_state.ey_df
    
    if not filtered_ey.empty:
        st.write(f"**Available EY Personnel ({len(filtered_ey)} found):**")
        
        # Display EY personnel
        selected_ey = st.selectbox("Select EY Personnel:", filtered_ey['NAME'].tolist(), key="ey_person_select")
        
        if selected_ey:
            # Show details
            ey_row = filtered_ey[filtered_ey['NAME'] == selected_ey].iloc[0]
            
            col_details1, col_details2 = st.columns(2)
            with col_details1:
                st.write(f"**ID:** {ey_row.get('ID_NUMBER', 'N/A')}")
                st.write(f"**Designation:** {ey_row.get('DESIGNATION', 'N/A')}")
            with col_details2:
                st.write(f"**Department:** {ey_row.get('DEPARTMENT', 'N/A')}")
                st.write(f"**Mobile:** {ey_row.get('MOBILE', 'N/A')}")
            
            # Allocation button
            if st.button(f"✅ Allocate {selected_ey} to Selected Dates", use_container_width=True):
                st.session_state.current_allocation_person = selected_ey
                st.session_state.current_allocation_ey_row = ey_row.to_dict()
                st.session_state.current_allocation_type = "EY"
                st.rerun()
    else:
        st.warning("No EY personnel found")
    
    # Handle EY allocation
    if st.session_state.current_allocation_person and st.session_state.current_allocation_type == "EY":
        # Show reference selection
        st.markdown(f"### 📋 Reference for {st.session_state.current_allocation_person}")
        ref_data = get_or_create_reference("EY Personnel")
        
        if ref_data is not None:
            # Perform allocation
            allocation_count, conflicts, warnings = perform_allocation_with_conflict_check(
                st.session_state.current_allocation_person,
                selected_date_shifts,
                "",
                "EY",
                ref_data
            )
            
            # Update exam data
            exam_key = st.session_state.current_exam_key
            if exam_key not in st.session_state.exam_data:
                st.session_state.exam_data[exam_key] = {}
            
            st.session_state.exam_data[exam_key]['ey_allocations'] = st.session_state.ey_allocation
            
            # Save data
            save_all_data()
            
            # Clear allocation state
            st.session_state.current_allocation_person = None
            st.session_state.current_allocation_ey_row = None
            st.session_state.current_allocation_type = None
            
            if allocation_count > 0:
                success_msg = f"✅ Allocated {st.session_state.current_allocation_person} to {allocation_count} date-shift combinations"
                
                if conflicts:
                    conflict_details = "\n".join([c['message'] for c in conflicts[:3]])
                    if len(conflicts) > 3:
                        conflict_details += f"\n... and {len(conflicts) - 3} more"
                    st.error(f"❌ {len(conflicts)} conflict(s) prevented allocation:\n\n{conflict_details}")
                
                st.success(success_msg)
                st.rerun()
            else:
                if conflicts:
                    st.error(f"❌ No allocations made due to {len(conflicts)} conflict(s)")
                else:
                    st.error("❌ No allocations made")
    
    # Current EY Allocations
    if st.session_state.ey_allocation:
        st.markdown("---")
        st.markdown("### 📋 Current EY Allocations")
        
        ey_df = pd.DataFrame(st.session_state.ey_allocation)
        
        # Filter by current exam
        current_ey = ey_df[ey_df['Exam'] == st.session_state.current_exam_key]
        
        if not current_ey.empty:
            st.dataframe(
                current_ey[['Sl. No.', 'EY Personnel', 'Venue', 'Date', 'Shift', 'Rate (₹)']],
                use_container_width=True,
                hide_index=True
            )

# ============================================================================
# REPORTS MODULE
# ============================================================================

def show_reports():
    """Display reports interface"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #ff8c00 0%, #ffa500 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📊 REPORTS & EXPORTS</h1>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Allocation Reports", "💰 Remuneration Reports"])
    
    with tab1:
        show_allocation_reports()
    
    with tab2:
        show_remuneration_reports()

def show_allocation_reports():
    """Display allocation reports"""
    st.markdown("### 📋 Allocation Reports")
    
    if not st.session_state.allocation and not st.session_state.ey_allocation:
        st.info("No allocation data available")
        return
    
    if st.session_state.allocation:
        alloc_df = pd.DataFrame(st.session_state.allocation)
        
        # Show summary
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("Total IO Allocations", len(alloc_df))
        with col_stat2:
            st.metric("Unique IOs", alloc_df['IO Name'].nunique())
        with col_stat3:
            st.metric("Total Days", alloc_df['Date'].nunique())
        
        # Show preview
        with st.expander("Preview IO Allocations"):
            st.dataframe(
                alloc_df[['Sl. No.', 'IO Name', 'Venue', 'Date', 'Shift', 'Role', 'Mock Test']].head(10),
                use_container_width=True,
                hide_index=True
            )
    
    if st.session_state.ey_allocation:
        st.markdown("##### EY Allocations")
        ey_df = pd.DataFrame(st.session_state.ey_allocation)
        
        col_ey1, col_ey2 = st.columns(2)
        with col_ey1:
            st.metric("Total EY Allocations", len(ey_df))
        with col_ey2:
            st.metric("Unique EY Personnel", ey_df['EY Personnel'].nunique())
        
        with st.expander("Preview EY Allocations"):
            st.dataframe(
                ey_df[['Sl. No.', 'EY Personnel', 'Venue', 'Date', 'Shift', 'Rate (₹)']].head(10),
                use_container_width=True,
                hide_index=True
            )

def show_remuneration_reports():
    """Display remuneration reports"""
    st.markdown("### 💰 Remuneration Reports")
    
    if not st.session_state.allocation and not st.session_state.ey_allocation:
        st.info("No allocation data available")
        return
    
    if st.session_state.allocation:
        # Calculate IO remuneration
        alloc_df = pd.DataFrame(st.session_state.allocation)
        
        total_io_amount = 0
        for (io_name, date), group in alloc_df.groupby(['IO Name', 'Date']):
            shifts = len(group)
            is_mock = any(group['Mock Test'])
            
            if is_mock:
                amount = st.session_state.remuneration_rates['mock_test']
            else:
                if shifts > 1:
                    amount = st.session_state.remuneration_rates['multiple_shifts']
                else:
                    amount = st.session_state.remuneration_rates['single_shift']
            
            total_io_amount += amount
        
        col_rem1, col_rem2 = st.columns(2)
        with col_rem1:
            st.metric("Total IO Remuneration", f"₹{total_io_amount:,}")
        
        # Calculate EY remuneration
        if st.session_state.ey_allocation:
            ey_df = pd.DataFrame(st.session_state.ey_allocation)
            total_ey_days = ey_df['Date'].nunique()
            total_ey_amount = total_ey_days * st.session_state.remuneration_rates['ey_personnel']
            
            with col_rem2:
                st.metric("Total EY Remuneration", f"₹{total_ey_amount:,}")
        
        # Grand total
        grand_total = total_io_amount + (total_ey_amount if 'total_ey_amount' in locals() else 0)
        st.metric("Grand Total", f"₹{grand_total:,}")

# ============================================================================
# SETTINGS MODULE
# ============================================================================

def show_settings():
    """Display system settings"""
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>⚙️ SYSTEM SETTINGS</h1>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["💰 Remuneration Rates", "🛠️ Data Management"])
    
    with tab1:
        show_remuneration_settings()
    
    with tab2:
        show_data_management()

def show_remuneration_settings():
    """Display remuneration rate settings"""
    st.markdown("### 💰 Remuneration Rates Configuration")
    
    col_rate1, col_rate2 = st.columns(2)
    
    with col_rate1:
        multiple_shifts = st.number_input(
            "Multiple Shifts (₹):",
            min_value=0,
            value=st.session_state.remuneration_rates['multiple_shifts'],
            step=50
        )
        
        single_shift = st.number_input(
            "Single Shift (₹):",
            min_value=0,
            value=st.session_state.remuneration_rates['single_shift'],
            step=50
        )
    
    with col_rate2:
        mock_test = st.number_input(
            "Mock Test (₹):",
            min_value=0,
            value=st.session_state.remuneration_rates['mock_test'],
            step=50
        )
        
        ey_personnel = st.number_input(
            "EY Personnel (₹ per day):",
            min_value=0,
            value=st.session_state.remuneration_rates['ey_personnel'],
            step=100
        )
    
    if st.button("💾 Save Rates", use_container_width=True):
        st.session_state.remuneration_rates = {
            'multiple_shifts': multiple_shifts,
            'single_shift': single_shift,
            'mock_test': mock_test,
            'ey_personnel': ey_personnel
        }
        
        save_all_data()
        st.success("✅ Remuneration rates saved!")

def show_data_management():
    """Display data management options"""
    st.markdown("### 🛠️ Data Management")
    
    # Backup Management
    st.markdown("#### 💾 Backup Management")
    
    col_back1, col_back2 = st.columns(2)
    
    with col_back1:
        backup_desc = st.text_input("Backup Description:", placeholder="Optional description")
        
        if st.button("🔒 Create New Backup", use_container_width=True):
            backup_file = create_backup(backup_desc)
            if backup_file:
                st.success(f"✅ Backup created: {backup_file.name}")
            else:
                st.error("❌ Failed to create backup")
    
    with col_back2:
        backup_files = list(BACKUP_DIR.glob("*.json"))
        if backup_files:
            backup_options = [f"{f.name}" for f in sorted(backup_files, reverse=True)]
            selected_backup = st.selectbox("Select Backup:", backup_options)
            
            if st.button("🔄 Restore Backup", type="secondary", use_container_width=True):
                backup_filename = selected_backup.split(" (")[0]
                backup_file = BACKUP_DIR / backup_filename
                
                if st.checkbox("I understand this will overwrite current data"):
                    if restore_from_backup(backup_file):
                        st.success("✅ Backup restored successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to restore backup")
        else:
            st.info("No backup files available")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""
    try:
        # Configure page
        st.set_page_config(
            page_title="SSC (ER) Kolkata - Enhanced Allocation System",
            page_icon="🏛️",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Apply custom CSS
        st.markdown("""
            <style>
            .main-header {
                text-align: center;
                padding: 1.5rem 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 10px;
                margin-bottom: 2rem;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }
            
            .card {
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                margin-bottom: 1rem;
            }
            
            .stButton > button {
                border-radius: 8px;
                font-weight: 500;
            }
            
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
            }
            
            .stTabs [data-baseweb="tab"] {
                height: 50px;
                background-color: #f8f9fa;
                border-radius: 8px 8px 0 0;
                font-weight: 500;
            }
            
            .stTabs [aria-selected="true"] {
                background-color: #4169e1;
                color: white;
            }
            
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
        """, unsafe_allow_html=True)
        
        # Initialize session state
        initialize_session_state()
        
        # Load existing data
        load_all_data()
        
        # Sidebar navigation
        with st.sidebar:
            st.markdown("""
                <div style='text-align: center; padding: 20px 0;'>
                    <h2>📋 Navigation</h2>
                    <p style='font-size: 0.9rem; color: #bdc3c7;'>Enhanced Date Selection System</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Menu selection
            menu_options = {
                "🏠 Dashboard": "dashboard",
                "📝 Exam Management": "exam",
                "👨‍💼 Centre Coordinator": "io",
                "👁️ EY Personnel": "ey",
                "📊 Reports": "reports",
                "⚙️ Settings": "settings"
            }
            
            selected_menu = st.radio(
                "Select Module:",
                list(menu_options.keys()),
                label_visibility="collapsed"
            )
            
            # Update session state
            st.session_state.menu = menu_options[selected_menu]
            
            st.markdown("---")
            
            # Current exam info
            st.markdown("### 🎯 Current Exam")
            if st.session_state.current_exam_key:
                st.success(f"**{st.session_state.current_exam_key[:30]}{'...' if len(st.session_state.current_exam_key) > 30 else ''}**")
                
                current_io = len([a for a in st.session_state.allocation 
                                if a.get('Exam') == st.session_state.current_exam_key])
                current_ey = len([a for a in st.session_state.ey_allocation 
                                if a.get('Exam') == st.session_state.current_exam_key])
                
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    st.metric("IO", current_io)
                with col_stat2:
                    st.metric("EY", current_ey)
            else:
                st.warning("No exam selected")
            
            st.markdown("---")
            
            # Quick actions
            st.markdown("### ⚡ Quick Actions")
            
            col_q1, col_q2 = st.columns(2)
            with col_q1:
                if st.button("💾 Save", use_container_width=True):
                    save_all_data()
                    st.success("Data saved!")
            
            with col_q2:
                if st.button("🔄 Refresh", use_container_width=True):
                    st.rerun()
            
            if st.button("📥 Load Defaults", use_container_width=True):
                load_default_master_data()
                st.rerun()
        
        # Main content area
        try:
            # Display selected module
            if st.session_state.menu == "dashboard":
                show_dashboard()
            elif st.session_state.menu == "exam":
                show_exam_management()
            elif st.session_state.menu == "io":
                show_centre_coordinator()
            elif st.session_state.menu == "ey":
                show_ey_personnel()
            elif st.session_state.menu == "reports":
                show_reports()
            elif st.session_state.menu == "settings":
                show_settings()
            else:
                show_dashboard()
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.code(traceback.format_exc())
    
    except Exception as e:
        st.error(f"Critical error: {str(e)}")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
