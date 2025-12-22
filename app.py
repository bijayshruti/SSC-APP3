"""
STAFF SELECTION COMMISSION (ER), KOLKATA
Centre Coordinator & Flying Squad Allocation System
Streamlit Web Application
Designed by Bijay Paswan

ENHANCED VERSION WITH COMPREHENSIVE DELETION & RECORD MANAGEMENT SYSTEM
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
from typing import Dict, List, Tuple, Optional, Any, Set
import traceback
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
from openpyxl.utils import get_column_letter
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Create necessary directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)
AUDIT_DIR = DATA_DIR / "audit_logs"
AUDIT_DIR.mkdir(exist_ok=True)

# File paths
CONFIG_FILE = DATA_DIR / "config.json"
DATA_FILE = DATA_DIR / "allocations_data.json"
REFERENCE_FILE = DATA_DIR / "allocation_references.json"
DELETED_RECORDS_FILE = DATA_DIR / "deleted_records.json"
AUDIT_LOG_FILE = AUDIT_DIR / f"audit_{datetime.now().strftime('%Y%m')}.json"
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
        'undo_stack': [],
        'redo_stack': [],
        
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
        'menu': 'dashboard',
        
        # Deletion system state
        'deletion_mode': None,
        'selected_deletions': [],
        'bulk_deletion_role_groups': {},
        'show_deletion_dialog': False,
        'deletion_order_no': "",
        'deletion_reason': "",
        'show_deleted_records': False,
        'deleted_records_filter': "all",
        'show_bulk_delete': False,
        'bulk_delete_selection': [],
        'last_action': None,
        'show_update_reference': False,
        'update_reference_data': None
    }
    
    # Initialize all values
    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# ============================================================================
# AUDIT LOGGING SYSTEM
# ============================================================================

def log_audit_event(event_type: str, event_data: Dict, user_action: str = ""):
    """Log audit events for compliance"""
    try:
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'event_data': event_data,
            'user_action': user_action,
            'exam': st.session_state.current_exam_key,
            'user': "system_admin"  # In production, replace with actual user
        }
        
        # Load existing audit log
        audit_log = []
        if AUDIT_LOG_FILE.exists():
            with open(AUDIT_LOG_FILE, 'r') as f:
                audit_log = json.load(f)
        
        # Append new entry
        audit_log.append(audit_entry)
        
        # Save audit log
        with open(AUDIT_LOG_FILE, 'w') as f:
            json.dump(audit_log, f, indent=2, default=str)
        
        return True
    except Exception as e:
        logging.error(f"Audit logging error: {str(e)}")
        return False

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
                    'ey_allocation': []
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
        
        # Log backup creation
        log_audit_event(
            event_type="backup_created",
            event_data={
                "backup_file": backup_file.name,
                "description": description,
                "record_count": {
                    "exams": len(st.session_state.exam_data),
                    "deleted_records": len(st.session_state.deleted_records)
                }
            },
            user_action="System backup"
        )
        
        return backup_file
    except Exception as e:
        return None

def restore_from_backup(backup_file):
    """Restore data from backup file"""
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        # Save current state to undo stack
        current_state = {
            'exam_data': st.session_state.exam_data.copy(),
            'allocation_references': st.session_state.allocation_references.copy(),
            'deleted_records': st.session_state.deleted_records.copy(),
            'current_exam_key': st.session_state.current_exam_key
        }
        st.session_state.undo_stack.append(current_state)
        
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
        
        # Log restoration
        log_audit_event(
            event_type="backup_restored",
            event_data={
                "backup_file": backup_file.name,
                "description": backup_data.get('description', ''),
                "timestamp": backup_data.get('timestamp', '')
            },
            user_action="Restored from backup"
        )
        
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

def format_currency(value):
    """Format value as currency"""
    try:
        if pd.isna(value):
            return "₹0"
        return f"₹{int(value):,}"
    except:
        return f"₹{value}"

def get_unique_key(prefix, index, extra=""):
    """Generate a unique key for Streamlit elements"""
    if st.session_state.current_exam_key:
        exam_part = st.session_state.current_exam_key.replace(" ", "_").replace("-", "_")
        return f"{prefix}_{exam_part}_{index}_{extra}_{datetime.now().timestamp()}"
    return f"{prefix}_{index}_{extra}_{datetime.now().timestamp()}"

# ============================================================================
# DATE SELECTION HELPER FUNCTIONS
# ============================================================================

def display_date_card(date_str, venue_data, venue_key, allocation_type):
    """Display a date card with shift selection"""
    
    # Get shifts for this date
    date_shifts = venue_data[venue_data['DATE'] == date_str]['SHIFT'].unique()
    date_shifts = [str(s) for s in date_shifts if pd.notna(s) and str(s) != '']
    
    date_key = f"{venue_key}_{date_str}"
    
    # Initialize date state if not exists
    if allocation_type == "IO":
        state_dict = st.session_state.date_grid_state['normal_dates']
    else:
        state_dict = st.session_state.date_grid_state['ey_dates']
    
    if venue_key not in state_dict:
        state_dict[venue_key] = {}
    
    if date_key not in state_dict[venue_key]:
        state_dict[venue_key][date_key] = {
            'all_selected': False,
            'shifts': {}
        }
    
    # Display date in a card
    with st.container():
        # Date header with expander
        expanded = st.session_state.date_grid_state['expanded_dates'].get(date_key, False)
        col_header, col_check = st.columns([3, 1])
        
        with col_header:
            st.markdown(f"**{date_str}**")
        
        with col_check:
            date_selected = st.checkbox(
                "✓ All",
                value=state_dict[venue_key][date_key].get('all_selected', False),
                key=get_unique_key("date_all", date_str),
                on_change=lambda dk=date_key, vk=venue_key: toggle_all_shifts(dk, vk, date_shifts, allocation_type)
            )
        
        # Shift selection
        if len(date_shifts) <= 3:
            # Display shifts inline
            for shift in date_shifts:
                shift_selected = st.checkbox(
                    shift,
                    value=state_dict[venue_key][date_key]['shifts'].get(shift, False),
                    key=get_unique_key("shift", date_str, shift),
                    on_change=lambda dk=date_key, vk=venue_key, s=shift: update_shift_selection(dk, vk, s, allocation_type)
                )
        else:
            # Use multiselect for many shifts
            selected_shifts = st.multiselect(
                "Select shifts:",
                date_shifts,
                default=[s for s in date_shifts if state_dict[venue_key][date_key]['shifts'].get(s, False)],
                key=get_unique_key("multishift", date_str)
            )
            
            # Update state
            for shift in date_shifts:
                state_dict[venue_key][date_key]['shifts'][shift] = (shift in selected_shifts)
            
            # Update "all selected" status
            if set(date_shifts) == set(selected_shifts):
                state_dict[venue_key][date_key]['all_selected'] = True
            elif selected_shifts:
                state_dict[venue_key][date_key]['all_selected'] = False
        
        st.markdown("---")

def toggle_all_shifts(date_key, venue_key, shifts, allocation_type):
    """Toggle all shifts for a date"""
    if allocation_type == "IO":
        state_dict = st.session_state.date_grid_state['normal_dates']
    else:
        state_dict = st.session_state.date_grid_state['ey_dates']
    
    current_state = state_dict[venue_key][date_key]
    new_state = not current_state.get('all_selected', False)
    
    for shift in shifts:
        state_dict[venue_key][date_key]['shifts'][shift] = new_state
    
    state_dict[venue_key][date_key]['all_selected'] = new_state

def update_shift_selection(date_key, venue_key, shift, allocation_type):
    """Update shift selection status"""
    if allocation_type == "IO":
        state_dict = st.session_state.date_grid_state['normal_dates']
    else:
        state_dict = st.session_state.date_grid_state['ey_dates']
    
    current_state = state_dict[venue_key][date_key]['shifts'].get(shift, False)
    state_dict[venue_key][date_key]['shifts'][shift] = not current_state
    
    # Update "all selected" status
    all_shifts = list(state_dict[venue_key][date_key]['shifts'].keys())
    if all(all_shifts):
        state_dict[venue_key][date_key]['all_selected'] = True
    else:
        state_dict[venue_key][date_key]['all_selected'] = False

def get_selected_date_shifts(venue_key, unique_dates, venue_data, allocation_type, selected_venues=None):
    """Get selected date-shift combinations"""
    selected_combinations = []
    
    if allocation_type == "IO":
        state_dict = st.session_state.date_grid_state['normal_dates']
        venues = [st.session_state.selected_venue]
    else:
        state_dict = st.session_state.date_grid_state['ey_dates']
        venues = selected_venues or [st.session_state.selected_venue]
    
    for venue in venues:
        venue_data_filtered = venue_data if venue == st.session_state.selected_venue else st.session_state.venue_df[st.session_state.venue_df['VENUE'] == venue]
        
        for date_str in unique_dates:
            date_key = f"{venue_key}_{date_str}"
            
            if venue_key in state_dict and date_key in state_dict[venue_key]:
                date_state = state_dict[venue_key][date_key]
                
                for shift, selected in date_state.get('shifts', {}).items():
                    if selected:
                        selected_combinations.append({
                            'venue': venue,
                            'date': date_str,
                            'shift': shift
                        })
    
    return selected_combinations

# ============================================================================
# DELETION SYSTEM - TIER 1: SINGLE ENTRY DELETION
# ============================================================================

def show_deletion_dialog(record, record_type="IO"):
    """Show deletion dialog for single entry"""
    
    st.markdown("### 🗑️ Delete Entry")
    
    # Display record info
    if record_type == "IO":
        st.write(f"**IO Name:** {record.get('IO Name', 'N/A')}")
        st.write(f"**Venue:** {record.get('Venue', 'N/A')}")
        st.write(f"**Date:** {record.get('Date', 'N/A')}")
        st.write(f"**Shift:** {record.get('Shift', 'N/A')}")
        st.write(f"**Role:** {record.get('Role', 'N/A')}")
    else:
        st.write(f"**EY Personnel:** {record.get('EY Personnel', 'N/A')}")
        st.write(f"**Venue:** {record.get('Venue', 'N/A')}")
        st.write(f"**Date:** {record.get('Date', 'N/A')}")
        st.write(f"**Shift:** {record.get('Shift', 'N/A')}")
    
    # Deletion reference inputs
    st.markdown("---")
    st.markdown("### 📋 Deletion Reference (Mandatory)")
    
    deletion_order_no = st.text_input(
        "Deletion Order No.:",
        placeholder="e.g., SSC/Deletion/2024/001",
        key=get_unique_key("del_order", record.get('Sl. No.', 0))
    )
    
    deletion_reason = st.text_area(
        "Deletion Reason:",
        placeholder="Explain why this allocation is being deleted...",
        height=100,
        key=get_unique_key("del_reason", record.get('Sl. No.', 0))
    )
    
    col_confirm, col_cancel = st.columns(2)
    
    with col_confirm:
        if st.button("✅ Confirm Deletion", type="primary", use_container_width=True):
            if not deletion_order_no.strip():
                st.error("❌ Deletion Order No. is required")
                return False
            if not deletion_reason.strip():
                st.error("❌ Deletion Reason is required")
                return False
            
            # Save to undo stack
            if record_type == "IO":
                undo_data = {
                    'action': 'delete_io',
                    'record': record.copy(),
                    'record_type': 'IO'
                }
            else:
                undo_data = {
                    'action': 'delete_ey',
                    'record': record.copy(),
                    'record_type': 'EY'
                }
            st.session_state.undo_stack.append(undo_data)
            
            # Perform deletion
            success = delete_single_entry(record, record_type, deletion_order_no, deletion_reason)
            
            if success:
                st.session_state.show_deletion_dialog = False
                st.session_state.deletion_mode = None
                st.rerun()
            return success
    
    with col_cancel:
        if st.button("❌ Cancel", type="secondary", use_container_width=True):
            st.session_state.show_deletion_dialog = False
            st.session_state.deletion_mode = None
            st.rerun()
    
    return False

def delete_single_entry(record, record_type, deletion_order_no, deletion_reason):
    """Delete single entry with audit trail"""
    
    try:
        # Create deletion record
        deletion_record = {
            'original_data': record,
            'deletion_order_no': deletion_order_no.strip(),
            'deletion_reason': deletion_reason.strip(),
            'deletion_timestamp': datetime.now().isoformat(),
            'exam': st.session_state.current_exam_key,
            'record_type': record_type,
            'deleted_by': 'system_admin'
        }
        
        # Add to deleted records
        st.session_state.deleted_records.append(deletion_record)
        
        # Remove from active allocations
        if record_type == "IO":
            # Remove by finding exact match
            for idx, alloc in enumerate(st.session_state.allocation):
                if (alloc.get('Sl. No.') == record.get('Sl. No.') and
                    alloc.get('IO Name') == record.get('IO Name') and
                    alloc.get('Venue') == record.get('Venue') and
                    alloc.get('Date') == record.get('Date') and
                    alloc.get('Shift') == record.get('Shift')):
                    
                    del st.session_state.allocation[idx]
                    
                    # Renumber serial numbers
                    for i, alloc in enumerate(st.session_state.allocation):
                        alloc['Sl. No.'] = i + 1
                    
                    break
        else:
            # EY allocation deletion
            for idx, alloc in enumerate(st.session_state.ey_allocation):
                if (alloc.get('Sl. No.') == record.get('Sl. No.') and
                    alloc.get('EY Personnel') == record.get('EY Personnel') and
                    alloc.get('Venue') == record.get('Venue') and
                    alloc.get('Date') == record.get('Date') and
                    alloc.get('Shift') == record.get('Shift')):
                    
                    del st.session_state.ey_allocation[idx]
                    
                    # Renumber serial numbers
                    for i, alloc in enumerate(st.session_state.ey_allocation):
                        alloc['Sl. No.'] = i + 1
                    
                    break
        
        # Update exam data
        exam_key = st.session_state.current_exam_key
        if exam_key in st.session_state.exam_data:
            st.session_state.exam_data[exam_key]['io_allocations'] = st.session_state.allocation
            st.session_state.exam_data[exam_key]['ey_allocations'] = st.session_state.ey_allocation
        
        # Save data
        save_all_data()
        
        # Log audit event
        log_audit_event(
            event_type="single_entry_deletion",
            event_data={
                "record_type": record_type,
                "record_id": record.get('Sl. No.', 'Unknown'),
                "person_name": record.get('IO Name') or record.get('EY Personnel', 'Unknown'),
                "deletion_order_no": deletion_order_no,
                "reason": deletion_reason[:100]  # Truncate for logging
            },
            user_action="Deleted single entry"
        )
        
        st.success(f"✅ Entry deleted successfully. Deletion Order: {deletion_order_no}")
        return True
        
    except Exception as e:
        st.error(f"❌ Error deleting entry: {str(e)}")
        return False

# ============================================================================
# ALLOCATION TABLE WITH DELETION OPTIONS (FIXED KEY ISSUE)
# ============================================================================

def show_allocation_table_with_controls():
    """Display allocation table with deletion options"""
    
    if not st.session_state.current_exam_key:
        st.info("No exam selected")
        return
    
    exam_key = st.session_state.current_exam_key
    
    # Header with controls
    col_header1, col_header2, col_header3, col_header4 = st.columns([2, 1, 1, 1])
    
    with col_header1:
        st.markdown(f"### 📋 Current Allocations - {exam_key}")
    
    with col_header2:
        if st.button("🗑️ Bulk Delete", use_container_width=True, key="bulk_delete_btn"):
            st.session_state.show_bulk_delete = True
            st.rerun()
    
    with col_header3:
        if st.button("↩️ Undo", use_container_width=True, disabled=len(st.session_state.undo_stack) == 0, key="undo_btn"):
            perform_undo()
            st.rerun()
    
    with col_header4:
        if st.button("↪️ Redo", use_container_width=True, disabled=len(st.session_state.redo_stack) == 0, key="redo_btn"):
            perform_redo()
            st.rerun()
    
    # Show IO allocations
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    
    if io_allocations:
        st.markdown("#### 👨‍💼 IO Allocations")
        
        # Create DataFrame for display
        io_display_data = []
        for alloc in io_allocations:
            io_display_data.append({
                'Sl. No.': alloc.get('Sl. No.', ''),
                'IO Name': alloc.get('IO Name', ''),
                'Venue': alloc.get('Venue', ''),
                'Date': alloc.get('Date', ''),
                'Shift': alloc.get('Shift', ''),
                'Role': alloc.get('Role', ''),
                'Mock': '✓' if alloc.get('Mock Test', False) else '',
                'Order No.': alloc.get('Order No.', ''),
                'Actions': alloc.get('Sl. No.', '')  # Placeholder for actions
            })
        
        if io_display_data:
            io_df = pd.DataFrame(io_display_data)
            
            # Display table
            st.dataframe(
                io_df[['Sl. No.', 'IO Name', 'Venue', 'Date', 'Shift', 'Role', 'Mock', 'Order No.']],
                use_container_width=True,
                hide_index=True
            )
            
            # Individual deletion controls - FIXED KEY ISSUE HERE
            st.markdown("##### Individual Deletion")
            
            for idx, alloc in enumerate(io_allocations):
                # Use a unique key based on allocation content, not just serial number
                unique_id = f"{alloc.get('IO Name', '')}_{alloc.get('Venue', '')}_{alloc.get('Date', '')}_{alloc.get('Shift', '')}"
                
                col_del1, col_del2, col_del3, col_del4, col_del5, col_del6 = st.columns([3, 2, 2, 1, 1, 1])
                
                with col_del1:
                    st.write(f"**{alloc.get('IO Name', '')}**")
                
                with col_del2:
                    st.write(f"{alloc.get('Venue', '')}")
                
                with col_del3:
                    st.write(f"{alloc.get('Date', '')} ({alloc.get('Shift', '')})")
                
                with col_del4:
                    st.write(f"{alloc.get('Role', '')}")
                
                with col_del5:
                    # Use unique_id in the key to prevent duplicates
                    if st.button("🗑️", key=f"del_io_{unique_id}_{idx}", help="Delete this entry"):
                        st.session_state.deletion_mode = "single"
                        st.session_state.selected_deletions = [alloc]
                        st.session_state.show_deletion_dialog = True
                        st.rerun()
                
                with col_del6:
                    if st.button("📝", key=f"edit_io_{unique_id}_{idx}", help="Edit this entry"):
                        st.warning("Edit functionality coming soon")
    
    # Show EY allocations
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if ey_allocations:
        st.markdown("---")
        st.markdown("#### 👁️ EY Allocations")
        
        # Create DataFrame for display
        ey_display_data = []
        for alloc in ey_allocations:
            ey_display_data.append({
                'Sl. No.': alloc.get('Sl. No.', ''),
                'EY Personnel': alloc.get('EY Personnel', ''),
                'Venue': alloc.get('Venue', ''),
                'Date': alloc.get('Date', ''),
                'Shift': alloc.get('Shift', ''),
                'Rate (₹)': alloc.get('Rate (₹)', ''),
                'Order No.': alloc.get('Order No.', ''),
                'Actions': alloc.get('Sl. No.', '')
            })
        
        if ey_display_data:
            ey_df = pd.DataFrame(ey_display_data)
            
            # Display table
            st.dataframe(
                ey_df[['Sl. No.', 'EY Personnel', 'Venue', 'Date', 'Shift', 'Rate (₹)', 'Order No.']],
                use_container_width=True,
                hide_index=True
            )
            
            # Individual deletion controls - FIXED KEY ISSUE HERE
            st.markdown("##### Individual Deletion")
            for idx, alloc in enumerate(ey_allocations):
                # Use a unique key based on allocation content
                unique_id = f"{alloc.get('EY Personnel', '')}_{alloc.get('Venue', '')}_{alloc.get('Date', '')}_{alloc.get('Shift', '')}"
                
                col_del1, col_del2, col_del3, col_del4, col_del5 = st.columns([3, 2, 2, 1, 1])
                
                with col_del1:
                    st.write(f"**{alloc.get('EY Personnel', '')}**")
                
                with col_del2:
                    st.write(f"{alloc.get('Venue', '')}")
                
                with col_del3:
                    st.write(f"{alloc.get('Date', '')} ({alloc.get('Shift', '')})")
                
                with col_del4:
                    st.write(f"₹{alloc.get('Rate (₹)', '')}")
                
                with col_del5:
                    # Use unique_id in the key to prevent duplicates
                    if st.button("🗑️", key=f"del_ey_{unique_id}_{idx}", help="Delete this entry"):
                        st.session_state.deletion_mode = "single"
                        st.session_state.selected_deletions = [alloc]
                        st.session_state.show_deletion_dialog = True
                        st.rerun()
    
    # Delete Last Entry button
    if io_allocations or ey_allocations:
        st.markdown("---")
        col_last1, col_last2 = st.columns([3, 1])
        
        with col_last1:
            st.info("Quick Actions:")
        
        with col_last2:
            if st.button("🗑️ Delete Last Entry", type="secondary", use_container_width=True, key="del_last_btn"):
                # Find most recent entry
                recent_io = io_allocations[-1] if io_allocations else None
                recent_ey = ey_allocations[-1] if ey_allocations else None
                
                if recent_io and recent_ey:
                    # Compare timestamps
                    io_time = datetime.fromisoformat(recent_io.get('Timestamp', '2000-01-01'))
                    ey_time = datetime.fromisoformat(recent_ey.get('Timestamp', '2000-01-01'))
                    
                    if io_time > ey_time:
                        recent = recent_io
                        record_type = "IO"
                    else:
                        recent = recent_ey
                        record_type = "EY"
                elif recent_io:
                    recent = recent_io
                    record_type = "IO"
                elif recent_ey:
                    recent = recent_ey
                    record_type = "EY"
                else:
                    st.warning("No entries to delete")
                    return
                
                st.session_state.deletion_mode = "single"
                st.session_state.selected_deletions = [recent]
                st.session_state.show_deletion_dialog = True
                st.rerun()
    
    # Show empty message if no allocations
    if not io_allocations and not ey_allocations:
        st.info("No allocations found for this exam")

# ============================================================================
# CENTRE COORDINATOR MODULE
# ============================================================================

def show_centre_coordinator():
    """Main Centre Coordinator allocation module"""
    
    if not st.session_state.current_exam_key:
        st.warning("⚠️ Please select or create an exam first from the Exam Management section")
        return
    
    st.markdown(f"""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>👨‍💼 CENTRE COORDINATOR ALLOCATION</h1>
            <p>Exam: {st.session_state.current_exam_key}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Check if master data is loaded
    if not st.session_state.io_master_loaded:
        st.error("❌ IO Master data not loaded!")
        if st.button("📥 Load Default IO Data"):
            load_default_master_data()
            st.rerun()
        return
    
    if not st.session_state.venue_master_loaded:
        st.error("❌ Venue Master data not loaded!")
        if st.button("📥 Load Default Venue Data"):
            load_default_master_data()
            st.rerun()
        return
    
    # Main allocation interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 👤 Select IO")
        
        # Filter by area
        if not st.session_state.io_df.empty:
            areas = ['All Areas'] + sorted(st.session_state.io_df['AREA'].dropna().unique().tolist())
            selected_area = st.selectbox("Filter by Area:", areas, key="io_area_filter")
            
            if selected_area == 'All Areas':
                filtered_io = st.session_state.io_df
            else:
                filtered_io = st.session_state.io_df[st.session_state.io_df['AREA'] == selected_area]
            
            # Display IO list
            if not filtered_io.empty:
                io_list = filtered_io['NAME'].tolist()
                selected_io = st.selectbox(
                    "Select IO:",
                    io_list,
                    key="io_select",
                    index=0
                )
                
                # Show IO details
                if selected_io:
                    io_details = filtered_io[filtered_io['NAME'] == selected_io].iloc[0]
                    with st.expander("👤 IO Details"):
                        st.write(f"**Area:** {io_details.get('AREA', 'N/A')}")
                        st.write(f"**Designation:** {io_details.get('DESIGNATION', 'N/A')}")
                        st.write(f"**Mobile:** {io_details.get('MOBILE', 'N/A')}")
                        st.write(f"**Email:** {io_details.get('EMAIL', 'N/A')}")
                        
                        # Check for existing allocations
                        existing_allocations = [
                            a for a in st.session_state.allocation 
                            if a.get('IO Name') == selected_io and a.get('Exam') == st.session_state.current_exam_key
                        ]
                        if existing_allocations:
                            st.warning(f"This IO already has {len(existing_allocations)} allocation(s)")
                            with st.expander("View Existing Allocations"):
                                for alloc in existing_allocations[:3]:  # Show first 3
                                    st.write(f"- {alloc.get('Venue')} on {alloc.get('Date')} ({alloc.get('Shift')})")
                                if len(existing_allocations) > 3:
                                    st.write(f"... and {len(existing_allocations) - 3} more")
            else:
                st.warning("No IOs found in selected area")
        else:
            st.error("IO data not available")
    
    with col2:
        st.markdown("### 🎯 Select Role")
        
        role_options = ["Centre Coordinator", "Flying Squad"]
        selected_role = st.radio(
            "Select Role:",
            role_options,
            horizontal=True,
            key="role_select"
        )
        
        # Show role-specific information
        if selected_role == "Centre Coordinator":
            st.info("🎯 **Centre Coordinator:** Overall in-charge of examination centre")
            rate = st.session_state.remuneration_rates['multiple_shifts']
        else:
            st.info("🚀 **Flying Squad:** Mobile supervision team")
            rate = st.session_state.remuneration_rates['single_shift']
        
        st.write(f"**Rate:** ₹{rate} per day")
    
    # Date and Shift Selection
    st.markdown("### 📅 Date & Shift Selection")
    
    # Create date selection grid
    selected_date_shifts = create_enhanced_date_selection_grid("IO")
    
    if selected_date_shifts:
        st.success(f"✅ Selected {len(selected_date_shifts)} date-shift combination(s)")
        
        # Show summary
        with st.expander("📋 View Selected Dates & Shifts"):
            for ds in selected_date_shifts:
                st.write(f"• {ds['venue']} - {ds['date']} ({ds['shift']})")
    
    # Allocation controls
    if selected_io and selected_date_shifts:
        st.markdown("### 🚀 Allocation Controls")
        
        col_alloc1, col_alloc2, col_alloc3 = st.columns([1, 1, 1])
        
        with col_alloc1:
            # Get reference info
            exam_key = st.session_state.current_exam_key
            role = selected_role
            
            # Check if reference exists
            reference_info = st.session_state.allocation_references.get(exam_key, {}).get(role, {})
            
            if reference_info:
                st.info(f"📋 **Current Reference:** {reference_info.get('order_no', 'N/A')}")
            else:
                st.warning("⚠️ No reference set for this role")
                if st.button("📝 Set Reference", key="set_ref_btn"):
                    st.session_state.creating_new_ref_IO = True
        
        with col_alloc2:
            # Calculate total amount
            total_shifts = len(selected_date_shifts)
            if selected_role == "Centre Coordinator":
                # Multiple shifts at same venue on same day count as one
                unique_days = set(f"{ds['venue']}_{ds['date']}" for ds in selected_date_shifts)
                total_amount = len(unique_days) * st.session_state.remuneration_rates['multiple_shifts']
            else:
                total_amount = total_shifts * st.session_state.remuneration_rates['single_shift']
            
            st.metric("💰 Total Amount", f"₹{total_amount}")
        
        with col_alloc3:
            # Allocate button
            if st.button("✅ Allocate Now", type="primary", use_container_width=True, key="allocate_btn"):
                if not reference_info and not st.session_state.creating_new_ref_IO:
                    st.error("Please set a reference before allocating")
                    return
                
                # Perform allocation
                success = allocate_io(
                    selected_io, 
                    selected_role, 
                    selected_date_shifts,
                    st.session_state.mock_test_mode
                )
                
                if success:
                    st.success("✅ Allocation successful!")
                    st.rerun()
        
        # Reference creation dialog
        if st.session_state.creating_new_ref_IO:
            show_reference_creation_dialog(selected_role)
    
    # Show current allocations for this IO
    if selected_io:
        show_current_io_allocations(selected_io)

def allocate_io(io_name, role, date_shifts, is_mock_test=False):
    """Allocate IO to selected dates and shifts"""
    
    try:
        # Get IO details
        io_details = st.session_state.io_df[st.session_state.io_df['NAME'] == io_name]
        if io_details.empty:
            st.error(f"IO '{io_name}' not found in master data")
            return False
        
        io_details = io_details.iloc[0]
        
        # Get reference info
        exam_key = st.session_state.current_exam_key
        reference_info = st.session_state.allocation_references.get(exam_key, {}).get(role, {})
        
        if not reference_info:
            st.error(f"No reference set for {role}")
            return False
        
        # Calculate serial number
        next_sl_no = len(st.session_state.allocation) + 1
        
        # Process each date-shift combination
        for ds in date_shifts:
            # Check for conflicts (same IO at same venue, date, shift)
            conflict = False
            for alloc in st.session_state.allocation:
                if (alloc.get('IO Name') == io_name and
                    alloc.get('Venue') == ds['venue'] and
                    alloc.get('Date') == ds['date'] and
                    alloc.get('Shift') == ds['shift'] and
                    alloc.get('Exam') == exam_key):
                    
                    conflict = True
                    st.warning(f"Conflict: {io_name} already allocated to {ds['venue']} on {ds['date']} ({ds['shift']})")
                    break
            
            if conflict:
                continue
            
            # Create allocation record
            allocation_record = {
                'Sl. No.': next_sl_no,
                'Exam': exam_key,
                'IO Name': io_name,
                'Area': io_details.get('AREA', ''),
                'Designation': io_details.get('DESIGNATION', ''),
                'Mobile': io_details.get('MOBILE', ''),
                'Email': io_details.get('EMAIL', ''),
                'Venue': ds['venue'],
                'Date': ds['date'],
                'Shift': ds['shift'],
                'Role': role,
                'Mock Test': is_mock_test,
                'Order No.': reference_info.get('order_no', ''),
                'Page No.': reference_info.get('page_no', ''),
                'Reference Remarks': reference_info.get('remarks', ''),
                'Timestamp': datetime.now().isoformat()
            }
            
            # Calculate remuneration
            if role == "Centre Coordinator":
                # Check if IO already has allocation at same venue on same day
                same_day_allocations = [
                    a for a in st.session_state.allocation 
                    if a.get('IO Name') == io_name and
                    a.get('Venue') == ds['venue'] and
                    a.get('Date') == ds['date'] and
                    a.get('Exam') == exam_key
                ]
                
                if same_day_allocations:
                    # Multiple shifts on same day - use multiple_shifts rate once
                    allocation_record['Rate (₹)'] = st.session_state.remuneration_rates['multiple_shifts']
                    allocation_record['Multiple Shifts'] = True
                else:
                    allocation_record['Rate (₹)'] = st.session_state.remuneration_rates['multiple_shifts']
                    allocation_record['Multiple Shifts'] = False
            else:
                # Flying Squad - single shift rate
                allocation_record['Rate (₹)'] = st.session_state.remuneration_rates['single_shifts']
                allocation_record['Multiple Shifts'] = False
            
            # Add to allocations
            st.session_state.allocation.append(allocation_record)
            next_sl_no += 1
        
        # Update exam data
        if exam_key not in st.session_state.exam_data:
            st.session_state.exam_data[exam_key] = {
                'io_allocations': [],
                'ey_allocations': []
            }
        
        st.session_state.exam_data[exam_key]['io_allocations'] = st.session_state.allocation
        
        # Save data
        save_all_data()
        
        # Log audit event
        log_audit_event(
            event_type="io_allocation",
            event_data={
                "io_name": io_name,
                "role": role,
                "date_shifts_count": len(date_shifts),
                "is_mock_test": is_mock_test,
                "order_no": reference_info.get('order_no', '')
            },
            user_action=f"Allocated {io_name} as {role}"
        )
        
        return True
        
    except Exception as e:
        st.error(f"Error allocating IO: {str(e)}")
        return False

def show_current_io_allocations(io_name):
    """Show current allocations for a specific IO"""
    
    exam_key = st.session_state.current_exam_key
    io_allocations = [
        a for a in st.session_state.allocation 
        if a.get('IO Name') == io_name and a.get('Exam') == exam_key
    ]
    
    if io_allocations:
        st.markdown("### 📋 Current Allocations for this IO")
        
        # Group by date
        allocations_by_date = {}
        for alloc in io_allocations:
            date_key = alloc.get('Date')
            if date_key not in allocations_by_date:
                allocations_by_date[date_key] = []
            allocations_by_date[date_key].append(alloc)
        
        # Display grouped allocations
        for date, allocs in sorted(allocations_by_date.items()):
            with st.expander(f"📅 {date} - {len(allocs)} shift(s)"):
                for alloc in allocs:
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    
                    with col1:
                        st.write(f"**{alloc.get('Venue')}**")
                    
                    with col2:
                        st.write(f"{alloc.get('Shift')}")
                    
                    with col3:
                        st.write(f"{alloc.get('Role')}")
                    
                    with col4:
                        if st.button("🗑️", key=f"del_existing_{alloc.get('Sl. No.', '')}", help="Delete"):
                            st.session_state.deletion_mode = "single"
                            st.session_state.selected_deletions = [alloc]
                            st.session_state.show_deletion_dialog = True
                            st.rerun()

def show_reference_creation_dialog(role):
    """Dialog for creating allocation references"""
    
    st.markdown("### 📝 Create Allocation Reference")
    
    exam_key = st.session_state.current_exam_key
    
    col_ref1, col_ref2 = st.columns(2)
    
    with col_ref1:
        order_no = st.text_input(
            "Order No.:",
            placeholder="e.g., SSC/Allocation/2024/001",
            key=f"ref_order_{role}"
        )
    
    with col_ref2:
        page_no = st.text_input(
            "Page No.:",
            placeholder="Page number",
            key=f"ref_page_{role}"
        )
    
    remarks = st.text_area(
        "Remarks (Optional):",
        placeholder="Any remarks about this allocation...",
        height=80,
        key=f"ref_remarks_{role}"
    )
    
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if st.button("💾 Save Reference", type="primary", use_container_width=True):
            if not order_no.strip():
                st.error("❌ Order No. is required")
                return
            
            # Save reference
            if exam_key not in st.session_state.allocation_references:
                st.session_state.allocation_references[exam_key] = {}
            
            st.session_state.allocation_references[exam_key][role] = {
                'order_no': order_no.strip(),
                'page_no': page_no.strip(),
                'remarks': remarks.strip(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Save data
            save_all_data()
            
            st.success(f"✅ Reference saved for {role}")
            st.session_state.creating_new_ref_IO = False
            st.rerun()
    
    with col_action2:
        if st.button("❌ Cancel", type="secondary", use_container_width=True):
            st.session_state.creating_new_ref_IO = False
            st.rerun()

# ============================================================================
# EY PERSONNEL MODULE
# ============================================================================

def show_ey_personnel():
    """Main EY Personnel allocation module"""
    
    if not st.session_state.current_exam_key:
        st.warning("⚠️ Please select or create an exam first from the Exam Management section")
        return
    
    st.markdown(f"""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #20b2aa 0%, #3cb371 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>👁️ EY PERSONNEL ALLOCATION</h1>
            <p>Exam: {st.session_state.current_exam_key}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Check if master data is loaded
    if not st.session_state.ey_master_loaded:
        st.error("❌ EY Personnel Master data not loaded!")
        if st.button("📥 Load Default EY Data"):
            load_default_master_data()
            st.rerun()
        return
    
    if not st.session_state.venue_master_loaded:
        st.error("❌ Venue Master data not loaded!")
        if st.button("📥 Load Default Venue Data"):
            load_default_master_data()
            st.rerun()
        return
    
    # Main allocation interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 👤 Select EY Personnel")
        
        if not st.session_state.ey_df.empty:
            # Filter options
            col_filter1, col_filter2 = st.columns(2)
            
            with col_filter1:
                universities = ['All Universities'] + sorted(st.session_state.ey_df['UNIVERSITY'].dropna().unique().tolist())
                selected_univ = st.selectbox("Filter by University:", universities, key="ey_univ_filter")
            
            with col_filter2:
                departments = ['All Departments'] + sorted(st.session_state.ey_df['DEPARTMENT'].dropna().unique().tolist())
                selected_dept = st.selectbox("Filter by Department:", departments, key="ey_dept_filter")
            
            # Apply filters
            filtered_ey = st.session_state.ey_df.copy()
            
            if selected_univ != 'All Universities':
                filtered_ey = filtered_ey[filtered_ey['UNIVERSITY'] == selected_univ]
            
            if selected_dept != 'All Departments':
                filtered_ey = filtered_ey[filtered_ey['DEPARTMENT'] == selected_dept]
            
            # Display EY list
            if not filtered_ey.empty:
                ey_list = filtered_ey['NAME'].tolist()
                selected_ey = st.selectbox(
                    "Select EY Personnel:",
                    ey_list,
                    key="ey_select",
                    index=0
                )
                
                # Show EY details
                if selected_ey:
                    ey_details = filtered_ey[filtered_ey['NAME'] == selected_ey].iloc[0]
                    with st.expander("👤 EY Personnel Details"):
                        st.write(f"**ID:** {ey_details.get('ID_NUMBER', 'N/A')}")
                        st.write(f"**University:** {ey_details.get('UNIVERSITY', 'N/A')}")
                        st.write(f"**Department:** {ey_details.get('DEPARTMENT', 'N/A')}")
                        st.write(f"**Designation:** {ey_details.get('DESIGNATION', 'N/A')}")
                        st.write(f"**Mobile:** {ey_details.get('MOBILE', 'N/A')}")
                        st.write(f"**Email:** {ey_details.get('EMAIL', 'N/A')}")
                        
                        # Check for existing allocations
                        existing_allocations = [
                            a for a in st.session_state.ey_allocation 
                            if a.get('EY Personnel') == selected_ey and a.get('Exam') == st.session_state.current_exam_key
                        ]
                        if existing_allocations:
                            st.warning(f"This EY Personnel already has {len(existing_allocations)} allocation(s)")
                            with st.expander("View Existing Allocations"):
                                for alloc in existing_allocations[:3]:
                                    st.write(f"- {alloc.get('Venue')} on {alloc.get('Date')} ({alloc.get('Shift')})")
                                if len(existing_allocations) > 3:
                                    st.write(f"... and {len(existing_allocations) - 3} more")
            else:
                st.warning("No EY Personnel found with selected filters")
        else:
            st.error("EY Personnel data not available")
    
    with col2:
        st.markdown("### 💰 Rate Information")
        
        rate = st.session_state.remuneration_rates['ey_personnel']
        st.info(f"**Standard Rate:** ₹{rate} per day")
        
        # Allow rate override if needed
        custom_rate = st.number_input(
            "Custom Rate (if different):",
            min_value=0,
            value=rate,
            step=500,
            key="ey_custom_rate"
        )
        
        st.write(f"**Final Rate:** ₹{custom_rate}")
    
    # Date and Shift Selection for EY
    st.markdown("### 📅 Date & Shift Selection")
    
    # Create date selection grid for EY
    selected_date_shifts = create_enhanced_date_selection_grid("EY")
    
    if selected_date_shifts:
        st.success(f"✅ Selected {len(selected_date_shifts)} date-shift combination(s)")
        
        # Show summary
        with st.expander("📋 View Selected Dates & Shifts"):
            for ds in selected_date_shifts:
                st.write(f"• {ds['venue']} - {ds['date']} ({ds['shift']})")
    
    # Allocation controls
    if selected_ey and selected_date_shifts:
        st.markdown("### 🚀 Allocation Controls")
        
        col_alloc1, col_alloc2, col_alloc3 = st.columns([1, 1, 1])
        
        with col_alloc1:
            # Get reference info
            exam_key = st.session_state.current_exam_key
            role = "EY Personnel"
            
            # Check if reference exists
            reference_info = st.session_state.allocation_references.get(exam_key, {}).get(role, {})
            
            if reference_info:
                st.info(f"📋 **Current Reference:** {reference_info.get('order_no', 'N/A')}")
            else:
                st.warning("⚠️ No reference set for EY Personnel")
                if st.button("📝 Set Reference", key="set_ey_ref_btn"):
                    st.session_state.creating_new_ref_EY_Personnel = True
        
        with col_alloc2:
            # Calculate total amount
            total_days = len(set(f"{ds['venue']}_{ds['date']}" for ds in selected_date_shifts))
            total_amount = total_days * custom_rate
            
            st.metric("💰 Total Amount", f"₹{total_amount}")
            st.caption(f"{total_days} day(s) × ₹{custom_rate}")
        
        with col_alloc3:
            # Allocate button
            if st.button("✅ Allocate Now", type="primary", use_container_width=True, key="allocate_ey_btn"):
                if not reference_info and not st.session_state.creating_new_ref_EY_Personnel:
                    st.error("Please set a reference before allocating")
                    return
                
                # Perform allocation
                success = allocate_ey(
                    selected_ey, 
                    selected_date_shifts,
                    custom_rate
                )
                
                if success:
                    st.success("✅ Allocation successful!")
                    st.rerun()
        
        # Reference creation dialog
        if st.session_state.creating_new_ref_EY_Personnel:
            show_ey_reference_creation_dialog()
    
    # Show current allocations for this EY Personnel
    if selected_ey:
        show_current_ey_allocations(selected_ey)

def allocate_ey(ey_name, date_shifts, rate):
    """Allocate EY Personnel to selected dates and shifts"""
    
    try:
        # Get EY details
        ey_details = st.session_state.ey_df[st.session_state.ey_df['NAME'] == ey_name]
        if ey_details.empty:
            st.error(f"EY Personnel '{ey_name}' not found in master data")
            return False
        
        ey_details = ey_details.iloc[0]
        
        # Get reference info
        exam_key = st.session_state.current_exam_key
        role = "EY Personnel"
        reference_info = st.session_state.allocation_references.get(exam_key, {}).get(role, {})
        
        if not reference_info:
            st.error(f"No reference set for {role}")
            return False
        
        # Calculate serial number
        next_sl_no = len(st.session_state.ey_allocation) + 1
        
        # Group by date to calculate daily rates
        allocations_by_date = {}
        for ds in date_shifts:
            date_key = f"{ds['venue']}_{ds['date']}"
            if date_key not in allocations_by_date:
                allocations_by_date[date_key] = []
            allocations_by_date[date_key].append(ds)
        
        # Process each day
        for date_key, day_shifts in allocations_by_date.items():
            # Check for conflicts
            conflict = False
            venue = day_shifts[0]['venue']
            date = day_shifts[0]['date']
            
            for alloc in st.session_state.ey_allocation:
                if (alloc.get('EY Personnel') == ey_name and
                    alloc.get('Venue') == venue and
                    alloc.get('Date') == date and
                    alloc.get('Exam') == exam_key):
                    
                    conflict = True
                    st.warning(f"Conflict: {ey_name} already allocated to {venue} on {date}")
                    break
            
            if conflict:
                continue
            
            # Create allocation record (one per day, not per shift)
            allocation_record = {
                'Sl. No.': next_sl_no,
                'Exam': exam_key,
                'EY Personnel': ey_name,
                'ID Number': ey_details.get('ID_NUMBER', ''),
                'University': ey_details.get('UNIVERSITY', ''),
                'Department': ey_details.get('DEPARTMENT', ''),
                'Designation': ey_details.get('DESIGNATION', ''),
                'Mobile': ey_details.get('MOBILE', ''),
                'Email': ey_details.get('EMAIL', ''),
                'Venue': venue,
                'Date': date,
                'Shifts': [s['shift'] for s in day_shifts],
                'Shift': ', '.join([s['shift'] for s in day_shifts]),
                'Rate (₹)': rate,
                'Order No.': reference_info.get('order_no', ''),
                'Page No.': reference_info.get('page_no', ''),
                'Reference Remarks': reference_info.get('remarks', ''),
                'Timestamp': datetime.now().isoformat()
            }
            
            # Add to allocations
            st.session_state.ey_allocation.append(allocation_record)
            next_sl_no += 1
        
        # Update exam data
        if exam_key not in st.session_state.exam_data:
            st.session_state.exam_data[exam_key] = {
                'io_allocations': [],
                'ey_allocations': []
            }
        
        st.session_state.exam_data[exam_key]['ey_allocations'] = st.session_state.ey_allocation
        
        # Save data
        save_all_data()
        
        # Log audit event
        log_audit_event(
            event_type="ey_allocation",
            event_data={
                "ey_name": ey_name,
                "date_shifts_count": len(date_shifts),
                "daily_rate": rate,
                "order_no": reference_info.get('order_no', '')
            },
            user_action=f"Allocated {ey_name} as EY Personnel"
        )
        
        return True
        
    except Exception as e:
        st.error(f"Error allocating EY Personnel: {str(e)}")
        return False

def show_current_ey_allocations(ey_name):
    """Show current allocations for a specific EY Personnel"""
    
    exam_key = st.session_state.current_exam_key
    ey_allocations = [
        a for a in st.session_state.ey_allocation 
        if a.get('EY Personnel') == ey_name and a.get('Exam') == exam_key
    ]
    
    if ey_allocations:
        st.markdown("### 📋 Current Allocations for this EY Personnel")
        
        # Display allocations
        for alloc in ey_allocations:
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            
            with col1:
                st.write(f"**{alloc.get('Venue')}**")
            
            with col2:
                st.write(f"{alloc.get('Date')}")
            
            with col3:
                st.write(f"{alloc.get('Shift')}")
            
            with col4:
                st.write(f"₹{alloc.get('Rate (₹)', '')}")
            
            with col5:
                if st.button("🗑️", key=f"del_ey_existing_{alloc.get('Sl. No.', '')}", help="Delete"):
                    st.session_state.deletion_mode = "single"
                    st.session_state.selected_deletions = [alloc]
                    st.session_state.show_deletion_dialog = True
                    st.rerun()

def show_ey_reference_creation_dialog():
    """Dialog for creating EY allocation references"""
    
    st.markdown("### 📝 Create EY Allocation Reference")
    
    exam_key = st.session_state.current_exam_key
    role = "EY Personnel"
    
    col_ref1, col_ref2 = st.columns(2)
    
    with col_ref1:
        order_no = st.text_input(
            "Order No.:",
            placeholder="e.g., SSC/EY/2024/001",
            key="ey_ref_order"
        )
    
    with col_ref2:
        page_no = st.text_input(
            "Page No.:",
            placeholder="Page number",
            key="ey_ref_page"
        )
    
    remarks = st.text_area(
        "Remarks (Optional):",
        placeholder="Any remarks about EY Personnel allocation...",
        height=80,
        key="ey_ref_remarks"
    )
    
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if st.button("💾 Save Reference", type="primary", use_container_width=True, key="save_ey_ref_btn"):
            if not order_no.strip():
                st.error("❌ Order No. is required")
                return
            
            # Save reference
            if exam_key not in st.session_state.allocation_references:
                st.session_state.allocation_references[exam_key] = {}
            
            st.session_state.allocation_references[exam_key][role] = {
                'order_no': order_no.strip(),
                'page_no': page_no.strip(),
                'remarks': remarks.strip(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Save data
            save_all_data()
            
            st.success(f"✅ Reference saved for {role}")
            st.session_state.creating_new_ref_EY_Personnel = False
            st.rerun()
    
    with col_action2:
        if st.button("❌ Cancel", type="secondary", use_container_width=True, key="cancel_ey_ref_btn"):
            st.session_state.creating_new_ref_EY_Personnel = False
            st.rerun()

# ============================================================================
# REPORTS MODULE
# ============================================================================

def show_reports():
    """Display reports and analytics"""
    
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #ff7e5f 0%, #feb47b 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>📊 REPORTS & ANALYTICS</h1>
            <p>Comprehensive Allocation Reports</p>
        </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.current_exam_key:
        st.warning("⚠️ Please select an exam to view reports")
        return
    
    exam_key = st.session_state.current_exam_key
    
    # Report selection
    report_type = st.selectbox(
        "Select Report Type:",
        ["📈 Summary Dashboard", "👨‍💼 IO Allocations Report", "👁️ EY Allocations Report", 
         "💰 Financial Summary", "📅 Date-wise Report", "🏢 Venue-wise Report"]
    )
    
    if report_type == "📈 Summary Dashboard":
        show_summary_dashboard(exam_key)
    elif report_type == "👨‍💼 IO Allocations Report":
        show_io_report(exam_key)
    elif report_type == "👁️ EY Allocations Report":
        show_ey_report(exam_key)
    elif report_type == "💰 Financial Summary":
        show_financial_summary(exam_key)
    elif report_type == "📅 Date-wise Report":
        show_datewise_report(exam_key)
    elif report_type == "🏢 Venue-wise Report":
        show_venuewise_report(exam_key)

def show_summary_dashboard(exam_key):
    """Show summary dashboard with charts"""
    
    # Get allocations for current exam
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_io = len(io_allocations)
        st.metric("👨‍💼 IO Allocations", total_io)
    
    with col2:
        total_ey = len(ey_allocations)
        st.metric("👁️ EY Allocations", total_ey)
    
    with col3:
        unique_ios = len(set(a.get('IO Name') for a in io_allocations))
        st.metric("Unique IOs", unique_ios)
    
    with col4:
        unique_venues = len(set(a.get('Venue') for a in io_allocations + ey_allocations))
        st.metric("Venues Covered", unique_venues)
    
    # Charts section
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # Role distribution
        if io_allocations:
            role_counts = {}
            for alloc in io_allocations:
                role = alloc.get('Role', 'Unknown')
                role_counts[role] = role_counts.get(role, 0) + 1
            
            if role_counts:
                fig = px.pie(
                    values=list(role_counts.values()),
                    names=list(role_counts.keys()),
                    title="IO Role Distribution",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        # Date distribution
        if io_allocations or ey_allocations:
            date_counts = {}
            for alloc in io_allocations + ey_allocations:
                date = alloc.get('Date', 'Unknown')
                date_counts[date] = date_counts.get(date, 0) + 1
            
            if date_counts:
                dates_sorted = sorted(date_counts.items(), key=lambda x: datetime.strptime(x[0], "%d-%m-%Y") if x[0] != 'Unknown' else datetime.min)
                dates = [d[0] for d in dates_sorted]
                counts = [d[1] for d in dates_sorted]
                
                fig = px.bar(
                    x=dates,
                    y=counts,
                    title="Allocations by Date",
                    labels={'x': 'Date', 'y': 'Number of Allocations'},
                    color=counts,
                    color_continuous_scale='Viridis'
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
    
    # Financial summary
    st.markdown("### 💰 Financial Summary")
    
    # Calculate IO costs
    io_cost = 0
    for alloc in io_allocations:
        io_cost += alloc.get('Rate (₹)', 0)
    
    # Calculate EY costs
    ey_cost = 0
    for alloc in ey_allocations:
        ey_cost += alloc.get('Rate (₹)', 0)
    
    total_cost = io_cost + ey_cost
    
    col_fin1, col_fin2, col_fin3 = st.columns(3)
    
    with col_fin1:
        st.metric("IO Costs", format_currency(io_cost))
    
    with col_fin2:
        st.metric("EY Costs", format_currency(ey_cost))
    
    with col_fin3:
        st.metric("Total Costs", format_currency(total_cost))

def show_io_report(exam_key):
    """Show detailed IO allocations report"""
    
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    
    if not io_allocations:
        st.info("No IO allocations for this exam")
        return
    
    # Filters
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        role_filter = st.multiselect(
            "Filter by Role:",
            options=sorted(set(a.get('Role') for a in io_allocations)),
            default=[]
        )
    
    with col_filter2:
        venue_filter = st.multiselect(
            "Filter by Venue:",
            options=sorted(set(a.get('Venue') for a in io_allocations)),
            default=[]
        )
    
    with col_filter3:
        date_filter = st.multiselect(
            "Filter by Date:",
            options=sorted(set(a.get('Date') for a in io_allocations)),
            default=[]
        )
    
    # Apply filters
    filtered_allocations = io_allocations
    
    if role_filter:
        filtered_allocations = [a for a in filtered_allocations if a.get('Role') in role_filter]
    
    if venue_filter:
        filtered_allocations = [a for a in filtered_allocations if a.get('Venue') in venue_filter]
    
    if date_filter:
        filtered_allocations = [a for a in filtered_allocations if a.get('Date') in date_filter]
    
    # Display report
    st.markdown(f"### 👨‍💼 IO Allocations Report ({len(filtered_allocations)} records)")
    
    if filtered_allocations:
        # Create DataFrame for display
        report_data = []
        for alloc in filtered_allocations:
            report_data.append({
                'Sl. No.': alloc.get('Sl. No.', ''),
                'IO Name': alloc.get('IO Name', ''),
                'Area': alloc.get('Area', ''),
                'Designation': alloc.get('Designation', ''),
                'Venue': alloc.get('Venue', ''),
                'Date': alloc.get('Date', ''),
                'Shift': alloc.get('Shift', ''),
                'Role': alloc.get('Role', ''),
                'Rate (₹)': alloc.get('Rate (₹)', ''),
                'Order No.': alloc.get('Order No.', ''),
                'Mock Test': 'Yes' if alloc.get('Mock Test', False) else 'No'
            })
        
        df = pd.DataFrame(report_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Summary statistics
        st.markdown("#### 📊 Summary Statistics")
        
        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
        
        with col_sum1:
            total_ios = len(set(a.get('IO Name') for a in filtered_allocations))
            st.metric("Unique IOs", total_ios)
        
        with col_sum2:
            total_cost = sum(a.get('Rate (₹)', 0) for a in filtered_allocations)
            st.metric("Total Cost", format_currency(total_cost))
        
        with col_sum3:
            avg_per_io = total_cost / max(total_ios, 1)
            st.metric("Avg per IO", format_currency(avg_per_io))
        
        with col_sum4:
            days_covered = len(set(a.get('Date') for a in filtered_allocations))
            st.metric("Days Covered", days_covered)
        
        # Export options
        st.markdown("#### 📤 Export Options")
        col_export1, col_export2 = st.columns(2)
        
        with col_export1:
            if st.button("📄 Export to Excel", use_container_width=True):
                export_io_report_to_excel(filtered_allocations, exam_key)
        
        with col_export2:
            if st.button("📊 Export Chart", use_container_width=True):
                export_io_charts(filtered_allocations)

def export_io_report_to_excel(allocations, exam_key):
    """Export IO report to Excel"""
    try:
        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "IO Allocations Report"
        
        # Add headers
        headers = ['Sl. No.', 'IO Name', 'Area', 'Designation', 'Venue', 'Date', 'Shift', 'Role', 'Rate (₹)', 'Order No.', 'Mock Test']
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
        
        # Add data
        for row_idx, alloc in enumerate(allocations, 2):
            ws.cell(row=row_idx, column=1, value=alloc.get('Sl. No.', ''))
            ws.cell(row=row_idx, column=2, value=alloc.get('IO Name', ''))
            ws.cell(row=row_idx, column=3, value=alloc.get('Area', ''))
            ws.cell(row=row_idx, column=4, value=alloc.get('Designation', ''))
            ws.cell(row=row_idx, column=5, value=alloc.get('Venue', ''))
            ws.cell(row=row_idx, column=6, value=alloc.get('Date', ''))
            ws.cell(row=row_idx, column=7, value=alloc.get('Shift', ''))
            ws.cell(row=row_idx, column=8, value=alloc.get('Role', ''))
            ws.cell(row=row_idx, column=9, value=alloc.get('Rate (₹)', ''))
            ws.cell(row=row_idx, column=10, value=alloc.get('Order No.', ''))
            ws.cell(row=row_idx, column=11, value='Yes' if alloc.get('Mock Test', False) else 'No')
        
        # Auto-size columns
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Save to bytes
        excel_buffer = BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)
        
        # Create download link
        b64 = base64.b64encode(excel_buffer.read()).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="IO_Allocations_{exam_key.replace(" ", "_")}.xlsx">📥 Download Excel File</a>'
        st.markdown(href, unsafe_allow_html=True)
        
        st.success("✅ Excel file generated successfully!")
        
    except Exception as e:
        st.error(f"Error generating Excel file: {str(e)}")

def show_ey_report(exam_key):
    """Show detailed EY allocations report"""
    
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if not ey_allocations:
        st.info("No EY allocations for this exam")
        return
    
    # Display report
    st.markdown(f"### 👁️ EY Allocations Report ({len(ey_allocations)} records)")
    
    # Create DataFrame for display
    report_data = []
    for alloc in ey_allocations:
        report_data.append({
            'Sl. No.': alloc.get('Sl. No.', ''),
            'EY Personnel': alloc.get('EY Personnel', ''),
            'ID Number': alloc.get('ID Number', ''),
            'University': alloc.get('University', ''),
            'Department': alloc.get('Department', ''),
            'Designation': alloc.get('Designation', ''),
            'Venue': alloc.get('Venue', ''),
            'Date': alloc.get('Date', ''),
            'Shift': alloc.get('Shift', ''),
            'Rate (₹)': alloc.get('Rate (₹)', ''),
            'Order No.': alloc.get('Order No.', '')
        })
    
    df = pd.DataFrame(report_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Summary statistics
    st.markdown("#### 📊 Summary Statistics")
    
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    
    with col_sum1:
        total_ey = len(set(a.get('EY Personnel') for a in ey_allocations))
        st.metric("Unique EY Personnel", total_ey)
    
    with col_sum2:
        total_cost = sum(a.get('Rate (₹)', 0) for a in ey_allocations)
        st.metric("Total Cost", format_currency(total_cost))
    
    with col_sum3:
        avg_per_ey = total_cost / max(total_ey, 1)
        st.metric("Avg per EY", format_currency(avg_per_ey))

def show_financial_summary(exam_key):
    """Show financial summary report"""
    
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if not io_allocations and not ey_allocations:
        st.info("No allocations for this exam")
        return
    
    # Calculate costs
    io_costs_by_role = {}
    for alloc in io_allocations:
        role = alloc.get('Role', 'Unknown')
        cost = alloc.get('Rate (₹)', 0)
        io_costs_by_role[role] = io_costs_by_role.get(role, 0) + cost
    
    total_io_cost = sum(io_costs_by_role.values())
    total_ey_cost = sum(a.get('Rate (₹)', 0) for a in ey_allocations)
    total_cost = total_io_cost + total_ey_cost
    
    # Display financial summary
    st.markdown("### 💰 Financial Summary")
    
    col_fin1, col_fin2 = st.columns(2)
    
    with col_fin1:
        st.metric("Total IO Costs", format_currency(total_io_cost))
        st.metric("Total EY Costs", format_currency(total_ey_cost))
        st.metric("Grand Total", format_currency(total_cost))
    
    with col_fin2:
        # Create pie chart
        labels = list(io_costs_by_role.keys()) + ['EY Personnel']
        values = list(io_costs_by_role.values()) + [total_ey_cost]
        
        if any(values):
            fig = px.pie(
                values=values,
                names=labels,
                title="Cost Distribution",
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Detailed breakdown
    st.markdown("#### 📊 Detailed Breakdown")
    
    # IO Costs by Role
    if io_costs_by_role:
        st.markdown("**IO Costs by Role:**")
        io_cost_df = pd.DataFrame({
            'Role': list(io_costs_by_role.keys()),
            'Cost': list(io_costs_by_role.values()),
            'Percentage': [f"{(v/total_io_cost*100):.1f}%" for v in io_costs_by_role.values()]
        })
        st.dataframe(io_cost_df, use_container_width=True, hide_index=True)
    
    # EY Costs
    if ey_allocations:
        st.markdown("**EY Personnel Costs:**")
        ey_cost = total_ey_cost
        ey_percentage = f"{(ey_cost/total_cost*100):.1f}%" if total_cost > 0 else "0%"
        st.write(f"Total EY Costs: {format_currency(ey_cost)} ({ey_percentage})")

def show_datewise_report(exam_key):
    """Show date-wise allocation report"""
    
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if not io_allocations and not ey_allocations:
        st.info("No allocations for this exam")
        return
    
    # Group by date
    date_data = {}
    
    for alloc in io_allocations:
        date = alloc.get('Date', 'Unknown')
        if date not in date_data:
            date_data[date] = {'io_count': 0, 'ey_count': 0, 'io_cost': 0, 'ey_cost': 0}
        date_data[date]['io_count'] += 1
        date_data[date]['io_cost'] += alloc.get('Rate (₹)', 0)
    
    for alloc in ey_allocations:
        date = alloc.get('Date', 'Unknown')
        if date not in date_data:
            date_data[date] = {'io_count': 0, 'ey_count': 0, 'io_cost': 0, 'ey_cost': 0}
        date_data[date]['ey_count'] += 1
        date_data[date]['ey_cost'] += alloc.get('Rate (₹)', 0)
    
    # Sort dates
    sorted_dates = []
    for date in date_data.keys():
        if date != 'Unknown':
            try:
                sorted_dates.append((datetime.strptime(date, "%d-%m-%Y"), date))
            except:
                sorted_dates.append((datetime.max, date))
        else:
            sorted_dates.append((datetime.max, date))
    
    sorted_dates.sort()
    
    # Display report
    st.markdown("### 📅 Date-wise Allocation Report")
    
    report_data = []
    for _, date in sorted_dates:
        data = date_data[date]
        report_data.append({
            'Date': date,
            'IO Allocations': data['io_count'],
            'EY Allocations': data['ey_count'],
            'Total Allocations': data['io_count'] + data['ey_count'],
            'IO Cost': format_currency(data['io_cost']),
            'EY Cost': format_currency(data['ey_cost']),
            'Total Cost': format_currency(data['io_cost'] + data['ey_cost'])
        })
    
    df = pd.DataFrame(report_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Create chart
    dates = [r['Date'] for r in report_data]
    io_counts = [r['IO Allocations'] for r in report_data]
    ey_counts = [r['EY Allocations'] for r in report_data]
    
    fig = go.Figure(data=[
        go.Bar(name='IO Allocations', x=dates, y=io_counts),
        go.Bar(name='EY Allocations', x=dates, y=ey_counts)
    ])
    
    fig.update_layout(
        title="Allocations by Date",
        xaxis_title="Date",
        yaxis_title="Number of Allocations",
        barmode='stack',
        xaxis_tickangle=-45
    )
    
    st.plotly_chart(fig, use_container_width=True)

def show_venuewise_report(exam_key):
    """Show venue-wise allocation report"""
    
    io_allocations = [a for a in st.session_state.allocation if a.get('Exam') == exam_key]
    ey_allocations = [a for a in st.session_state.ey_allocation if a.get('Exam') == exam_key]
    
    if not io_allocations and not ey_allocations:
        st.info("No allocations for this exam")
        return
    
    # Group by venue
    venue_data = {}
    
    for alloc in io_allocations:
        venue = alloc.get('Venue', 'Unknown')
        if venue not in venue_data:
            venue_data[venue] = {'io_count': 0, 'ey_count': 0, 'io_cost': 0, 'ey_cost': 0}
        venue_data[venue]['io_count'] += 1
        venue_data[venue]['io_cost'] += alloc.get('Rate (₹)', 0)
    
    for alloc in ey_allocations:
        venue = alloc.get('Venue', 'Unknown')
        if venue not in venue_data:
            venue_data[venue] = {'io_count': 0, 'ey_count': 0, 'io_cost': 0, 'ey_cost': 0}
        venue_data[venue]['ey_count'] += 1
        venue_data[venue]['ey_cost'] += alloc.get('Rate (₹)', 0)
    
    # Display report
    st.markdown("### 🏢 Venue-wise Allocation Report")
    
    report_data = []
    for venue, data in sorted(venue_data.items()):
        report_data.append({
            'Venue': venue,
            'IO Allocations': data['io_count'],
            'EY Allocations': data['ey_count'],
            'Total Allocations': data['io_count'] + data['ey_count'],
            'IO Cost': format_currency(data['io_cost']),
            'EY Cost': format_currency(data['ey_cost']),
            'Total Cost': format_currency(data['io_cost'] + data['ey_cost'])
        })
    
    df = pd.DataFrame(report_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Create chart
    venues = [r['Venue'] for r in report_data]
    io_counts = [r['IO Allocations'] for r in report_data]
    ey_counts = [r['EY Allocations'] for r in report_data]
    
    fig = px.bar(
        x=venues,
        y=[io_counts, ey_counts],
        title="Allocations by Venue",
        labels={'x': 'Venue', 'value': 'Number of Allocations'},
        barmode='stack'
    )
    
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# DELETION SYSTEM - TIER 2: BULK DELETION (Continued from earlier)
# ============================================================================

def show_bulk_delete_interface():
    """Show bulk deletion interface"""
    
    st.markdown("### 🗑️ Bulk Delete - Multiple Entries")
    
    # Search and filter options
    col_search1, col_search2, col_search3 = st.columns(3)
    
    with col_search1:
        search_name = st.text_input("Search by Name:", placeholder="Name contains...", key="bulk_search_name")
    
    with col_search2:
        search_venue = st.text_input("Search by Venue:", placeholder="Venue contains...", key="bulk_search_venue")
    
    with col_search3:
        search_date = st.date_input("Filter by Date:", key="bulk_search_date")
    
    # Type filter
    record_type = st.radio(
        "Record Type:",
        ["All", "IO Allocations", "EY Allocations"],
        horizontal=True,
        key="bulk_record_type"
    )
    
    # Get allocations based on filters
    all_allocations = []
    
    if record_type in ["All", "IO Allocations"]:
        for alloc in st.session_state.allocation:
            if alloc.get('Exam') == st.session_state.current_exam_key:
                all_allocations.append({
                    'record': alloc,
                    'type': 'IO',
                    'display': f"👨‍💼 {alloc.get('IO Name', 'N/A')} - {alloc.get('Venue', 'N/A')} - {alloc.get('Date', 'N/A')} ({alloc.get('Shift', 'N/A')})"
                })
    
    if record_type in ["All", "EY Allocations"]:
        for alloc in st.session_state.ey_allocation:
            if alloc.get('Exam') == st.session_state.current_exam_key:
                all_allocations.append({
                    'record': alloc,
                    'type': 'EY',
                    'display': f"👁️ {alloc.get('EY Personnel', 'N/A')} - {alloc.get('Venue', 'N/A')} - {alloc.get('Date', 'N/A')} ({alloc.get('Shift', 'N/A')})"
                })
    
    # Apply filters
    filtered_allocations = all_allocations
    
    if search_name:
        filtered_allocations = [
            a for a in filtered_allocations 
            if search_name.lower() in str(a['record'].get('IO Name') or a['record'].get('EY Personnel', '')).lower()
        ]
    
    if search_venue:
        filtered_allocations = [
            a for a in filtered_allocations 
            if search_venue.lower() in str(a['record'].get('Venue', '')).lower()
        ]
    
    if search_date:
        date_str = search_date.strftime("%d-%m-%Y")
        filtered_allocations = [
            a for a in filtered_allocations 
            if str(a['record'].get('Date', '')) == date_str
        ]
    
    if not filtered_allocations:
        st.info("No allocations match your search criteria")
        return
    
    # Multi-select for bulk deletion
    st.markdown(f"**Found {len(filtered_allocations)} allocation(s)**")
    
    # Create checkboxes for selection with unique keys
    selected_indices = []
    for idx, alloc in enumerate(filtered_allocations):
        unique_key = get_unique_key("bulk_select", idx, alloc['record'].get('IO Name') or alloc['record'].get('EY Personnel', ''))
        if st.checkbox(alloc['display'], key=unique_key):
            selected_indices.append(idx)
    
    if selected_indices:
        st.success(f"✅ Selected {len(selected_indices)} allocation(s) for deletion")
        
        # Group by role/type for separate references
        st.session_state.bulk_deletion_role_groups = {}
        for idx in selected_indices:
            alloc = filtered_allocations[idx]
            record_type = alloc['type']
            
            if record_type == 'IO':
                role = alloc['record'].get('Role', 'Unknown')
                group_key = f"IO_{role}"
            else:
                group_key = "EY"
            
            if group_key not in st.session_state.bulk_deletion_role_groups:
                st.session_state.bulk_deletion_role_groups[group_key] = []
            
            st.session_state.bulk_deletion_role_groups[group_key].append(alloc['record'])
        
        # Show role groups
        st.markdown("#### 📊 Deletion Groups (by Role)")
        for group_key, records in st.session_state.bulk_deletion_role_groups.items():
            st.write(f"**{group_key}:** {len(records)} record(s)")
        
        # Action buttons
        col_bulk1, col_bulk2 = st.columns(2)
        
        with col_bulk1:
            if st.button("🗑️ Proceed with Bulk Delete", type="primary", use_container_width=True, key="proceed_bulk_btn"):
                st.session_state.show_deletion_dialog = True
                st.session_state.deletion_mode = "bulk"
                st.rerun()
        
        with col_bulk2:
            if st.button("❌ Clear Selection", type="secondary", use_container_width=True, key="clear_bulk_btn"):
                st.session_state.bulk_delete_selection = []
                st.rerun()
    else:
        st.info("Select allocations above to proceed with bulk deletion")

# ============================================================================
# SETTINGS MODULE
# ============================================================================

def show_settings():
    """Display settings and configuration"""
    
    st.markdown("""
        <div style='text-align: center; padding: 20px; background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); 
                 color: white; border-radius: 10px; margin-bottom: 30px;'>
            <h1>⚙️ SYSTEM SETTINGS</h1>
            <p>Configuration & Administration</p>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["💰 Remuneration Rates", "📁 Data Management", "🛠️ System Tools"])
    
    with tab1:
        show_remuneration_settings()
    
    with tab2:
        show_data_management()
    
    with tab3:
        show_system_tools()

def show_remuneration_settings():
    """Display remuneration rate settings"""
    
    st.markdown("### 💰 Remuneration Rate Configuration")
    
    col_rate1, col_rate2 = st.columns(2)
    
    with col_rate1:
        st.session_state.remuneration_rates['multiple_shifts'] = st.number_input(
            "Centre Coordinator Rate (Multiple Shifts):",
            min_value=0,
            value=st.session_state.remuneration_rates['multiple_shifts'],
            step=50,
            key="rate_multiple"
        )
        
        st.session_state.remuneration_rates['single_shift'] = st.number_input(
            "Flying Squad Rate (Single Shift):",
            min_value=0,
            value=st.session_state.remuneration_rates['single_shift'],
            step=50,
            key="rate_single"
        )
    
    with col_rate2:
        st.session_state.remuneration_rates['mock_test'] = st.number_input(
            "Mock Test Rate:",
            min_value=0,
            value=st.session_state.remuneration_rates['mock_test'],
            step=50,
            key="rate_mock"
        )
        
        st.session_state.remuneration_rates['ey_personnel'] = st.number_input(
            "EY Personnel Rate:",
            min_value=0,
            value=st.session_state.remuneration_rates['ey_personnel'],
            step=500,
            key="rate_ey"
        )
    
    if st.button("💾 Save Rates", type="primary", key="save_rates_btn"):
        save_all_data()
        st.success("✅ Rates saved successfully!")

def show_data_management():
    """Display data management options"""
    
    st.markdown("### 📁 Data Management")
    
    # Backup management
    st.markdown("#### 💾 Backup Management")
    
    col_backup1, col_backup2 = st.columns(2)
    
    with col_backup1:
        backup_desc = st.text_input("Backup Description:", placeholder="Optional description...", key="backup_desc")
        
        if st.button("📥 Create Backup", use_container_width=True, key="create_backup_btn"):
            backup_file = create_backup(backup_desc)
            if backup_file:
                st.success(f"✅ Backup created: {backup_file.name}")
            else:
                st.error("❌ Failed to create backup")
    
    with col_backup2:
        # List existing backups
        backup_files = list(BACKUP_DIR.glob("*.json"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if backup_files:
            backup_options = [f"{f.name} ({f.stat().st_size/1024:.1f} KB)" for f in backup_files]
            selected_backup = st.selectbox("Select Backup:", backup_options, key="select_backup")
            
            if st.button("🔄 Restore Backup", type="secondary", use_container_width=True, key="restore_backup_btn"):
                backup_index = backup_options.index(selected_backup)
                backup_file = backup_files[backup_index]
                
                if restore_from_backup(backup_file):
                    st.success(f"✅ Backup restored from {backup_file.name}")
                    st.rerun()
                else:
                    st.error("❌ Failed to restore backup")
        else:
            st.info("No backups available")
    
    # Data import/export
    st.markdown("#### 📤 Import/Export")
    
    col_import1, col_import2 = st.columns(2)
    
    with col_import1:
        st.markdown("**Import Master Data:**")
        
        io_file = st.file_uploader("IO Master Data (Excel/CSV)", type=['xlsx', 'xls', 'csv'], key="io_upload")
        if io_file:
            try:
                if io_file.name.endswith('.csv'):
                    df = pd.read_csv(io_file)
                else:
                    df = pd.read_excel(io_file)
                
                required_cols = ['NAME', 'AREA', 'MOBILE', 'EMAIL', 'DESIGNATION']
                if all(col in df.columns for col in required_cols):
                    st.session_state.io_df = df
                    st.session_state.io_master_loaded = True
                    st.success(f"✅ IO data loaded: {len(df)} records")
                else:
                    st.error("❌ Missing required columns")
            except Exception as e:
                st.error(f"Error loading file: {str(e)}")
    
    with col_import2:
        st.markdown("**Export Data:**")
        
        if st.button("📄 Export All Data", use_container_width=True, key="export_all_btn"):
            # Create a comprehensive export
            export_all_data()

def show_system_tools():
    """Display system tools"""
    
    st.markdown("### 🛠️ System Tools")
    
    # System information
    st.markdown("#### ℹ️ System Information")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.write("**Data Statistics:**")
        st.write(f"- Exams: {len(st.session_state.exam_data)}")
        st.write(f"- IO Allocations: {len(st.session_state.allocation)}")
        st.write(f"- EY Allocations: {len(st.session_state.ey_allocation)}")
        st.write(f"- Deleted Records: {len(st.session_state.deleted_records)}")
    
    with col_info2:
        st.write("**Session State:**")
        st.write(f"- Current Exam: {st.session_state.current_exam_key or 'None'}")
        st.write(f"- Undo Stack: {len(st.session_state.undo_stack)}")
        st.write(f"- Redo Stack: {len(st.session_state.redo_stack)}")
    
    # Maintenance tools
    st.markdown("#### 🔧 Maintenance Tools")
    
    col_tool1, col_tool2 = st.columns(2)
    
    with col_tool1:
        if st.button("🔄 Reindex Allocations", use_container_width=True, key="reindex_btn"):
            # Reindex IO allocations
            for i, alloc in enumerate(st.session_state.allocation):
                alloc['Sl. No.'] = i + 1
            
            # Reindex EY allocations
            for i, alloc in enumerate(st.session_state.ey_allocation):
                alloc['Sl. No.'] = i + 1
            
            save_all_data()
            st.success("✅ Allocations reindexed successfully!")
    
    with col_tool2:
        if st.button("🧹 Clear All Data", type="secondary", use_container_width=True, key="clear_all_btn"):
            st.warning("⚠️ This will clear ALL data including allocations and exams!")
            confirm = st.checkbox("I understand this action cannot be undone")
            
            if confirm and st.button("☢️ CONFIRM CLEAR ALL", type="primary", key="confirm_clear_btn"):
                # Create backup first
                create_backup("BEFORE_CLEAR_ALL")
                
                # Clear all data
                st.session_state.exam_data = {}
                st.session_state.allocation = []
                st.session_state.ey_allocation = []
                st.session_state.allocation_references = {}
                st.session_state.current_exam_key = ""
                
                # Clear files
                for file in [DATA_FILE, REFERENCE_FILE]:
                    if file.exists():
                        file.unlink()
                
                save_all_data()
                st.success("✅ All data cleared!")
                st.rerun()

def export_all_data():
    """Export all system data"""
    try:
        # Create a comprehensive export structure
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'system_version': '1.0',
            'exam_data': st.session_state.exam_data,
            'allocation_references': st.session_state.allocation_references,
            'remuneration_rates': st.session_state.remuneration_rates,
            'deleted_records': st.session_state.deleted_records,
            'current_exam_key': st.session_state.current_exam_key
        }
        
        # Convert to JSON
        json_data = json.dumps(export_data, indent=4, default=str)
        
        # Create download link
        b64 = base64.b64encode(json_data.encode()).decode()
        href = f'<a href="data:application/json;base64,{b64}" download="SSC_System_Export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json">📥 Download Complete System Data</a>'
        st.markdown(href, unsafe_allow_html=True)
        
        st.success("✅ Export file generated successfully!")
        
    except Exception as e:
        st.error(f"Error exporting data: {str(e)}")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""
    try:
        # Configure page
        st.set_page_config(
            page_title="SSC (ER) Kolkata - Enhanced Deletion System",
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
            
            /* Deletion warning colors */
            .deletion-warning {
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 10px;
                margin: 10px 0;
            }
            
            .audit-record {
                background-color: #f8f9fa;
                border-left: 4px solid #6c757d;
                padding: 10px;
                margin: 5px 0;
                border-radius: 4px;
            }
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
                    <p style='font-size: 0.9rem; color: #bdc3c7;'>Enhanced Deletion System</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Menu selection
            menu_options = {
                "🏠 Dashboard": "dashboard",
                "📝 Exam Management": "exam",
                "👨‍💼 Centre Coordinator": "io",
                "👁️ EY Personnel": "ey",
                "📊 Reports": "reports",
                "🗑️ Deleted Records": "deleted_records",
                "📋 References": "references",
                "⚙️ Settings": "settings"
            }
            
            selected_menu = st.radio(
                "Select Module:",
                list(menu_options.keys()),
                label_visibility="collapsed",
                key="sidebar_menu"
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
            
            # Quick actions with undo/redo
            st.markdown("### ⚡ Quick Actions")
            
            col_q1, col_q2, col_q3 = st.columns(3)
            
            with col_q1:
                if st.button("💾 Save", use_container_width=True, key="sidebar_save"):
                    save_all_data()
                    st.success("Data saved!")
            
            with col_q2:
                undo_disabled = len(st.session_state.undo_stack) == 0
                if st.button("↩️ Undo", use_container_width=True, disabled=undo_disabled, key="sidebar_undo"):
                    perform_undo()
                    st.rerun()
            
            with col_q3:
                redo_disabled = len(st.session_state.redo_stack) == 0
                if st.button("↪️ Redo", use_container_width=True, disabled=redo_disabled, key="sidebar_redo"):
                    perform_redo()
                    st.rerun()
            
            if st.button("📥 Load Defaults", use_container_width=True, key="sidebar_load_defaults"):
                load_default_master_data()
                st.rerun()
        
        # Main content area
        try:
            # Handle deletion dialogs first
            if st.session_state.show_deletion_dialog:
                if st.session_state.deletion_mode == "single" and st.session_state.selected_deletions:
                    record = st.session_state.selected_deletions[0]
                    record_type = "IO" if 'IO Name' in record else "EY"
                    show_deletion_dialog(record, record_type)
                elif st.session_state.deletion_mode == "bulk":
                    show_bulk_deletion_dialog()
            
            # Handle bulk delete interface
            if st.session_state.show_bulk_delete:
                show_bulk_delete_interface()
                if st.button("← Back to Allocations", use_container_width=True, key="back_from_bulk"):
                    st.session_state.show_bulk_delete = False
                    st.rerun()
                return
            
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
            elif st.session_state.menu == "deleted_records":
                # Note: Deleted records functions need to be imported from earlier code
                # For now, we'll show a placeholder
                st.markdown("### 🗑️ Deleted Records Manager")
                st.info("Deleted records management module")
                # show_deleted_records_manager() would go here
            elif st.session_state.menu == "references":
                # Note: Reference management functions need to be imported from earlier code
                st.markdown("### 📋 Reference Management")
                st.info("Reference management module")
                # show_reference_management() would go here
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
